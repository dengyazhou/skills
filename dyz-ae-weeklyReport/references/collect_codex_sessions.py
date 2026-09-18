#!/usr/bin/env python3
"""提取 Codex 会话中每个 rollout 的首条真实用户提问。

用法:
    python3 collect_codex_sessions.py <sessions_dir> <YYYY> <MM> <DD> [<DD> ...]

需要剥离两类噪声:
  1. reviewer 会话  - 首条 user 消息以 "The following is the Codex agent history" 开头
  2. AGENTS.md 前缀 - 真实提问被 "# AGENTS.md ... </INSTRUCTIONS>" 包裹
"""
import glob
import json
import os
import re
import sys

NOISE_PATTERNS = [
    (r'^# AGENTS\.md.*?</INSTRUCTIONS>\s*', ''),
    (r'^The following is the Codex agent history.*', '[reviewer]'),
    (r'<user_instructions>.*?</user_instructions>', ''),
    (r'<environment_context>.*?</environment_context>', ''),
    (r'<plugins_instructions>.*?</plugins_instructions>', ''),
    (r'<skills_instructions>.*?</skills_instructions>', ''),
]


def clean(text):
    for pattern, repl in NOISE_PATTERNS:
        text = re.sub(pattern, repl, text, flags=re.S)
    return text.strip()


def extract_text(payload):
    """从 rollout 一行的 payload 中取出 user 消息文本, 非 user 消息返回 None。"""
    if not isinstance(payload, dict):
        return None
    message = payload.get("message")
    role = payload.get("role") or (message.get("role") if isinstance(message, dict) else None)
    if role != "user":
        return None
    content = payload.get("content")
    if not isinstance(content, list) and isinstance(message, dict):
        content = message.get("content") or []
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        for block in content:
            if isinstance(block, dict):
                text = block.get("text") or block.get("content") or ""
                if text:
                    return text
    return ""


def first_real_prompt(path):
    with open(path) as handle:
        for line in handle:
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                continue
            text = extract_text(record.get("payload") or record)
            if text is None:
                continue
            text = clean(text)
            if not text:
                continue
            if text.startswith("[reviewer]"):
                return "[reviewer session]"
            return text.replace("\n", " ").strip()
    return "(none)"


def main():
    if len(sys.argv) < 5:
        print(__doc__)
        return 1
    base, year, month = sys.argv[1], sys.argv[2], sys.argv[3]
    for day in sys.argv[4:]:
        for path in sorted(glob.glob(os.path.join(base, year, month, day, "*.jsonl"))):
            stamp = os.path.basename(path)[8:24]
            print(f"[{stamp}] {first_real_prompt(path)[:160]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
