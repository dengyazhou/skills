#!/usr/bin/env python3
"""拉取 IM 群中指定对象的发言及其话题闭环结论, 供周报「数小智反馈与闭环」章节使用。

用法:
    python3 collect_im_chat.py <chat_id> <open_id> <since_YYYY-MM-DD> <until_YYYY-MM-DD> [gap_minutes]

对应 OKR: 「构建技术支持知识沉淀闭环, 反哺智能客服与排查能力」O2 的 KR
「常态化使用数小智辅助答疑, 主动反馈答案质量 >= 30 次; 基于缺口提炼改进建议并推动落地」。

设计要点:
  - 锚点: sender.id == open_id 且 sender_type == 'user' 的消息, 时间落在 [since, until) 内。
  - 话题切分: 以锚点为起点向后扩展, 相邻真人消息间隔 <= gap_minutes(默认 90) 视为同一话题;
    间隔超限即终止。这样一次连续讨论 = 一个话题, 不会把几天后无关的讨论吸进来。
  - 例外: reply_to 指向本人发言的回复, 无论间隔多久都纳入(闭环结论常在稍后才出现)。
  - 机器人(sender_type == 'app')消息一律剔除, 否则数小智日报会淹没输出。
  - 实际拉取范围比 [since, until] 多 2 天, 以覆盖"周五发言、周末才闭环"。
  - 本脚本只负责"捞全 + 切话题"; 一条话题里有几个独立缺陷/建议条目由上层归纳判断。
"""
import json
import re
import subprocess
import sys
from datetime import datetime, timedelta

FMT = "%Y-%m-%d %H:%M"
TAG_RE = re.compile(r"</?p>|<br\s*/?>")


def fetch(chat_id, start, end):
    args = ["lark-cli", "im", "+chat-messages-list",
            "--chat-id", chat_id,
            "--start", start, "--end", end,
            "--order", "asc", "--page-all", "--page-limit", "1000",
            "--no-reactions", "--as", "user", "--format", "json"]
    proc = subprocess.run(args, capture_output=True, text=True)
    try:
        payload = json.loads(proc.stdout)
    except json.JSONDecodeError:
        print("lark-cli 输出无法解析: " + (proc.stderr or proc.stdout)[:500], file=sys.stderr)
        return None
    if not payload.get("ok"):
        print("lark-cli 调用失败: " + json.dumps(payload.get("error"), ensure_ascii=False),
              file=sys.stderr)
        return None
    return payload["data"]["messages"]


def is_human(m):
    return (m.get("sender") or {}).get("sender_type") == "user"


def sid(m):
    return (m.get("sender") or {}).get("id")


def sname(m):
    return (m.get("sender") or {}).get("name") or sid(m)


def brief(m, limit=200):
    text = TAG_RE.sub(" ", m.get("content") or "")
    return re.sub(r"\s+", " ", text).strip()[:limit]


def main():
    if len(sys.argv) < 5:
        print(__doc__)
        return 1
    chat_id, open_id, since_s, until_s = sys.argv[1:5]
    gap = timedelta(minutes=float(sys.argv[5]) if len(sys.argv) > 5 else 90)

    since = datetime.strptime(since_s, "%Y-%m-%d")
    until_end = datetime.strptime(until_s, "%Y-%m-%d") + timedelta(days=1)
    fetch_end = (until_end + timedelta(days=2)).strftime("%Y-%m-%d")

    msgs = fetch(chat_id, since_s, fetch_end)
    if msgs is None:
        return 1

    rows = []
    for m in msgs:
        if not is_human(m):
            continue
        try:
            rows.append((datetime.strptime(m["create_time"], FMT), m))
        except (KeyError, ValueError):
            continue
    rows.sort(key=lambda x: x[0])

    mine_ids = {m.get("message_id") for _, m in rows if sid(m) == open_id}
    anchors = [(t, m) for t, m in rows if sid(m) == open_id and since <= t < until_end]
    if not anchors:
        print("窗口 %s~%s 内该对象无发言" % (since_s, until_s))
        return 0

    # 以锚点为种子, 按消息间隔切分话题; 回应本人的消息强制纳入
    topics, cur = [], None
    for t, m in rows:
        if sid(m) == open_id and since <= t < until_end:
            if cur is None or t - cur[-1][0] > gap:
                cur = []
                topics.append(cur)
            cur.append((t, m))
            continue
        if cur is None:
            continue
        if m.get("reply_to") in mine_ids:
            cur.append((t, m))
        elif t - cur[-1][0] <= gap:
            cur.append((t, m))

    print("# chat=%s open_id=%s window=%s~%s gap=%smin"
          % (chat_id, open_id, since_s, until_s, int(gap.total_seconds() // 60)))
    print("# 锚点 %d 条, 切分为 %d 个话题\n" % (len(anchors), len(topics)))

    for idx, topic in enumerate(topics, 1):
        mine = [x for x in topic if sid(x[1]) == open_id]
        others = [x for x in topic if sid(x[1]) != open_id]
        replies = [x for x in others if x[1].get("reply_to") in mine_ids]
        print("===== 话题 %d: %s ~ %s | 本人 %d 条 / 他人 %d 条(其中直接回应本人 %d 条)%s ====="
              % (idx, topic[0][0].strftime(FMT), topic[-1][0].strftime(FMT),
                 len(mine), len(others), len(replies),
                 " ⚠ 无他人回应" if not others else ""))
        for t, m in topic:
            if sid(m) == open_id:
                tag = "★本人"
            elif m.get("reply_to") in mine_ids:
                tag = "↩回应"
            else:
                tag = "  他人"
            names = [x.get("name") for x in (m.get("mentions") or []) if x.get("name")]
            mt = (" @" + ",".join(names)) if names else ""
            print("  [%s] %s %s%s: %s" % (tag, t.strftime(FMT), sname(m), mt, brief(m)))
        print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
