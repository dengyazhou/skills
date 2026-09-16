#!/usr/bin/env python3
"""ae-diagnose-studio-archive-weekly-report: 经内部堡垒机收集 diagnose-studio 本周归档统计快照。

用法:
  python3 collect_stat.py [--search <主机搜索词>] [--db <远程 DB 路径>]
                          [--since YYYY-MM-DD] [--key <pem>] [--outfile <path>]

默认值（每次执行自动拉取本周最新数据）:
  --search 运维-技术交付测试机-腾讯云-刘路
  --db     /root/diagnose-studio/studio/studio.db
  --since  本周一 00:00（自动计算；窗口=本周一 → 服务器当前时刻，含当日最新）
  --key    ~/.ssh/dyz_inner.jumpserver.pem
输出: 带 NOW 时间戳的各节制表符文本（--outfile 则同时落盘）。

口径 —— 归档按 archives.source 分三类：
  - web          网页端发起人工排查      → 计入统计
  - mcp          [mcp]数小智 通道发起     → **也属用户真实使用，计入统计**（第 8 节给来源明细）
  - scan-import  批量导入历史归档         → 单列（第九节），不计入统计
    （归档目录扫描入库，created_at 是导入时刻而非原始排查时刻，内容为更早时间的历史问题）
故统计口径 = 「排除 scan-import」（而非仅取 source='web'；早期 source 为空的记录也按此计入）。

说明: 勿以历史快照/旧对话数字替代现场运行结果。
"""
import argparse, base64, datetime, os, re, sys, time

import paramiko

DEF_HOST, DEF_PORT, DEF_USER = "jumpserver-inner-v4.thinkingdata.cn", 2222, "dengyazhou"
DEF_KEY = os.path.expanduser("~/.ssh/dyz_inner.jumpserver.pem")
DEF_SEARCH = "运维-技术交付测试机-腾讯云-刘路"
DEF_DB = "/root/diagnose-studio/studio/studio.db"


def this_monday() -> str:
    today = datetime.date.today()
    return (today - datetime.timedelta(days=today.weekday())).strftime("%Y-%m-%d")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--search", default=DEF_SEARCH)
    ap.add_argument("--db", default=DEF_DB)
    ap.add_argument("--since", default=this_monday())
    ap.add_argument("--key", default=DEF_KEY)
    ap.add_argument("--outfile", default="")
    args = ap.parse_args()
    since = args.since  # YYYY-MM-DD

    WK = f"a.created_at >= '{since} 00:00:00'"
    # MCP 来源（[mcp]数小智 通道）：属用户真实使用，计入统计；此子查询仅用于「来源明细」备注
    MCPONLY = ("a.id IN (SELECT a2.id FROM archives a2 JOIN tasks t "
               "ON a2.dir_path LIKE t.archive_path || '%' "
               f"WHERE a2.created_at >= '{since} 00:00:00' AND t.source='mcp')")
    # 批量导入历史归档（source='scan-import'）：created_at=导入时刻、内容为更早历史，不计入统计
    EXCL_SCAN = "COALESCE(NULLIF(TRIM(a.source),''),'') <> 'scan-import'"
    # 统计口径（含 web 与 mcp）＝ 排除 scan-import
    HUMAN = f"{WK} AND {EXCL_SCAN}"
    SCAN = f"{WK} AND COALESCE(NULLIF(TRIM(a.source),''),'') = 'scan-import'"
    ST = "COALESCE(NULLIF(TRIM(a.outcome),''),'none')"
    CL = "CASE WHEN COALESCE(NULLIF(TRIM(a.cluster),''),'')='ID:' THEN 'Garena' " \
         "WHEN COALESCE(NULLIF(TRIM(a.cluster),''),'')='' THEN '(空)' ELSE a.cluster END"

    sqls = [
        ("0.总数", f"SELECT COUNT(*) total_all, SUM(created_at >= '{since} 00:00:00') week_cnt FROM archives"),
        ("1.本周来源分布", f"SELECT COALESCE(NULLIF(TRIM(source),''),'(空)') src, COUNT(*) n "
                          f"FROM archives WHERE created_at >= '{since} 00:00:00' GROUP BY src ORDER BY n DESC"),
        ("2.全量状态(含各类来源)", f"SELECT {ST} st, COUNT(*) n FROM archives a WHERE {WK} GROUP BY st"),
        ("3.统计口径skill×outcome", f"SELECT a.skill_id, {ST} st, COUNT(*) n FROM archives a "
                                   f"WHERE {HUMAN} GROUP BY a.skill_id, st ORDER BY a.skill_id"),
        ("4.统计口径每人×状态", f"SELECT u.username, {ST} st, COUNT(*) n FROM archives a "
                              f"JOIN users u ON u.id=a.owner_id WHERE {HUMAN} GROUP BY u.username, st ORDER BY u.username"),
        ("5.统计口径unresolved(fix)", f"SELECT u.username, a.skill_id, a.created_at, "
                                     "COALESCE(a.fix_status,'') fix, COALESCE(a.fix_optimized_at,'') fixat, "
                                     "substr(COALESCE(a.fix_note,''),1,30) note "
                                     f"FROM archives a JOIN users u ON u.id=a.owner_id WHERE {HUMAN} "
                                     "AND TRIM(a.outcome)='unresolved' ORDER BY a.skill_id, a.created_at"),
        ("6.统计口径未标记清单", f"SELECT u.username, a.created_at, "
                               "COALESCE(NULLIF(TRIM(a.source),''),'(空)') src, a.skill_id, "
                               + CL.replace("'(空)'", "'-'") + ", "
                               "substr(replace(replace(a.question, char(10),' '), char(13),' '),1,70) q "
                               f"FROM archives a JOIN users u ON u.id=a.owner_id WHERE {HUMAN} "
                               f"AND {ST}='none' ORDER BY a.created_at"),
        ("7.统计口径cluster分布", f"SELECT {CL} cl, COUNT(*) n FROM archives a WHERE {HUMAN} GROUP BY cl ORDER BY n DESC"),
        ("8.MCP来源明细(已计入统计)", f"SELECT u.username, {ST} st, COUNT(*) n FROM archives a "
                                    f"JOIN users u ON u.id=a.owner_id WHERE {HUMAN} AND {MCPONLY} "
                                    "GROUP BY u.username, st ORDER BY u.username"),
        ("8b.MCP来源时间范围", f"SELECT MIN(a.created_at), MAX(a.created_at), COUNT(*) FROM archives a WHERE {MCPONLY}"),
        ("8c.web来源明细(已计入统计)", f"SELECT u.username, {ST} st, COUNT(*) n FROM archives a "
                                     f"JOIN users u ON u.id=a.owner_id WHERE {HUMAN} AND NOT ({MCPONLY}) "
                                     "GROUP BY u.username, st ORDER BY u.username"),
        ("9.批量导入scan-import(单列,不计入)", f"SELECT a.skill_id, {ST} st, COUNT(*) n FROM archives a "
                                             f"WHERE {SCAN} GROUP BY a.skill_id, st ORDER BY a.skill_id"),
        ("9b.scan-import时间范围", f"SELECT MIN(a.created_at), MAX(a.created_at), COUNT(*) FROM archives a WHERE {SCAN}"),
    ]

    lines = []
    cli = paramiko.SSHClient()
    cli.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    cli.connect(DEF_HOST, port=DEF_PORT, username=DEF_USER, key_filename=args.key,
                timeout=30, allow_agent=False, look_for_keys=False)
    ch = cli.invoke_shell(term="xterm", width=320, height=100)

    def drain(seconds):
        buf = b""
        deadline = time.time() + seconds
        while time.time() < deadline:
            if ch.recv_ready():
                buf += ch.recv(65536)
            time.sleep(0.2)
        return buf.decode("utf-8", "replace")

    def wait_until(patterns, timeout):
        buf = b""
        deadline = time.time() + timeout
        while time.time() < deadline:
            if ch.recv_ready():
                buf += ch.recv(65536)
            txt = buf.decode("utf-8", "replace")
            for name, pat in patterns.items():
                if re.search(pat, txt):
                    return name, txt
            time.sleep(0.2)
        return None, txt

    def run(cmd, timeout=120):
        ch.send(cmd + '; echo "__RC_$?__"\n')
        _, out = wait_until({"rc": r"__RC_\d+__"}, timeout=timeout)
        res, skip = [], True
        for ln in out.splitlines():
            if skip:
                skip = False
                continue
            if re.match(r"^__RC_\d+__$", ln.strip()):
                continue
            res.append(ln)
        return "\n".join(res)

    def q(sql):
        src = ("import sqlite3,base64,time\n"
               "print('NOW', time.strftime('%Y-%m-%d %H:%M:%S'))\n"
               "c=sqlite3.connect('" + args.db + "')\n"
               "cur=c.cursor()\n"
               "for stmt in base64.b64decode('" + base64.b64encode(sql.encode()).decode() + "').decode().split(';'):\n"
               "    stmt=stmt.strip()\n"
               "    if not stmt: continue\n"
               "    try:\n"
               "        cur.execute(stmt)\n"
               "    except Exception as e:\n"
               "        print('ERR', e); continue\n"
               "    rows=cur.fetchall()\n"
               "    print('ROWS', len(rows))\n"
               "    [print('\\t'.join(str(x) for x in r)) for r in rows]\n")
        b64 = base64.b64encode(src.encode()).decode()
        return run("echo " + b64 + " | base64 -d | python3 - 2>&1")

    try:
        banner = drain(6)
        if "Opt>" not in banner:
            ch.send("\r")
            drain(4)
        ch.send(args.search + "\r")
        m, out = wait_until({"[root@": r"\[root@.*[#$]", "fail": r"Opt>|\[Host\]>"}, timeout=60)
        if m != "[root@":
            lines.append("登录失败: " + out[-800:])
        else:
            lines.append(f"# window: {since} 00:00:00 ~ now(远端当前时刻)；每次执行自动拉取本周最新数据")
            lines.append(f"# db={args.db} search={args.search}")
            for title, sql in sqls:
                lines.append(f"== {title} ==")
                lines.append(q(sql))
    finally:
        try:
            ch.send("exit\n")
            time.sleep(0.5)
        except Exception:
            pass
        cli.close()

    out = "\n".join(lines)
    print(out)
    if args.outfile:
        with open(args.outfile, "w", encoding="utf-8") as f:
            f.write(out + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
