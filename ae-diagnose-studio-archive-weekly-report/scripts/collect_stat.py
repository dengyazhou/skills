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
    MCP = ("a.id NOT IN (SELECT a2.id FROM archives a2 JOIN tasks t "
           "ON a2.dir_path LIKE t.archive_path || '%' "
           f"WHERE a2.created_at >= '{since} 00:00:00' AND t.source='mcp')")
    CL = "CASE WHEN COALESCE(NULLIF(TRIM(a.cluster),''),'')='ID:' THEN 'Garena' " \
         "WHEN COALESCE(NULLIF(TRIM(a.cluster),''),'')='' THEN '(空)' ELSE a.cluster END"

    sqls = [
        ("0.总数", f"SELECT COUNT(*) total_all, SUM(created_at >= '{since} 00:00:00') week_cnt FROM archives"),
        ("1.全量状态", "SELECT COALESCE(NULLIF(TRIM(outcome),''),'none') st, COUNT(*) n FROM archives WHERE "
                       f"created_at >= '{since} 00:00:00' GROUP BY st"),
        ("2.mcp自动化清单", "SELECT a.id, a.skill_id, a.created_at FROM archives a JOIN tasks t "
                           f"ON a.dir_path LIKE t.archive_path || '%' WHERE {WK} AND t.source='mcp' ORDER BY a.created_at"),
        ("3.人工skill×outcome", "SELECT a.skill_id, COALESCE(NULLIF(TRIM(a.outcome),''),'none') st, COUNT(*) n "
                                f"FROM archives a WHERE {WK} AND {MCP} GROUP BY a.skill_id, st ORDER BY a.skill_id"),
        ("4.人工每人×状态", "SELECT u.username, COALESCE(NULLIF(TRIM(a.outcome),''),'none') st, COUNT(*) n "
                           f"FROM archives a JOIN users u ON u.id=a.owner_id WHERE {WK} AND {MCP} "
                           "GROUP BY u.username, st ORDER BY u.username"),
        ("5.人工unresolved(fix)", "SELECT u.username, a.skill_id, a.created_at, COALESCE(a.fix_status,'') fix, "
                                  "COALESCE(a.fix_optimized_at,'') fixat, "
                                  "substr(COALESCE(a.fix_note,''),1,30) note "
                                  f"FROM archives a JOIN users u ON u.id=a.owner_id WHERE {WK} AND {MCP} "
                                  "AND TRIM(a.outcome)='unresolved' ORDER BY a.skill_id, a.created_at"),
        ("6.人工未标记清单", "SELECT u.username, a.created_at, a.skill_id, " +
                            CL.replace("'(空)'", "'-'") + " cl, " +
                            "substr(replace(replace(a.question, char(10),' '), char(13),' '),1,70) q "
                            f"FROM archives a JOIN users u ON u.id=a.owner_id WHERE {WK} AND {MCP} "
                            "AND COALESCE(NULLIF(TRIM(a.outcome),''),'none')='none' ORDER BY a.created_at"),
        ("7.人工cluster分布", f"SELECT {CL} cl, COUNT(*) n FROM archives a WHERE {WK} AND {MCP} "
                              "GROUP BY cl ORDER BY n DESC"),
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
