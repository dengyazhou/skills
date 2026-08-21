#!/usr/bin/env python3
"""拉取指定用户在给定时间窗内编辑过的飞书文档。

用法:
    python3 collect_feishu_docs.py <open_id> <since_YYYY-MM-DD> [max_pages]

注意: docs +search 返回结果按 last_open_time 排序而非 update_time,
因此不能因遇到一条旧文档就提前 break, 必须翻满 max_pages。
"""
import json
import subprocess
import sys
from datetime import datetime


def collect(open_id, since_ts, max_pages=15):
    seen, docs, page_token = set(), [], ""
    for _ in range(max_pages):
        args = ["lark-cli", "docs", "+search", "--query", "", "--as", "user",
                "--format", "json", "--page-size", "20"]
        if page_token:
            args += ["--page-token", page_token]
        proc = subprocess.run(args, capture_output=True, text=True)
        try:
            payload = json.loads(proc.stdout)
        except json.JSONDecodeError:
            break
        if not payload.get("ok"):
            break
        data = payload["data"]
        for item in data.get("results", []):
            meta = item["result_meta"]
            token = meta.get("token")
            if token in seen:
                continue
            seen.add(token)
            if meta.get("update_time", 0) < since_ts:
                continue
            if meta.get("edit_user_id") != open_id:
                continue
            docs.append((meta.get("update_time_iso"), meta.get("doc_types"),
                         item["title_highlighted"], meta.get("url")))
        if not data.get("has_more"):
            break
        page_token = data.get("page_token", "")
        if not page_token:
            break
    docs.sort(reverse=True)
    return docs, len(seen)


def main():
    if len(sys.argv) < 3:
        print(__doc__)
        return 1
    open_id = sys.argv[1]
    since_ts = int(datetime.strptime(sys.argv[2], "%Y-%m-%d").timestamp())
    max_pages = int(sys.argv[3]) if len(sys.argv) > 3 else 15
    docs, scanned = collect(open_id, since_ts, max_pages)
    for updated, doc_type, title, url in docs:
        print(f"[{updated}] {doc_type} | {title}")
        print(f"    {url}")
    print(f"\ntotal {len(docs)} / scanned {scanned}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
