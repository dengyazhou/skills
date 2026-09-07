---
name: ae-diagnose-studio-archive-weekly-report
description: 汇总 diagnose-studio（数据排查工作台 Web Studio）部署上的本周归档统计，生成「占比优先」样式的飞书云文档并同步。当用户需要查看 diagnose-studio / 数据排查工作台的历史归档统计（本周多少个会话、每人多少、已解决/未定位/未标记占比、按 skill/客户分布、未定位优化状态、自动化通道单列），或要把该统计同步/刷新到飞书文档时使用。也承接「重新拉一下数据同步飞书」「归档统计周报」「看下已解决/未定位占比」等说法。默认数据源：内部堡垒机 jumpserver-inner-v4 上 ta1（运维-技术交付测试机-腾讯云-刘路）的 /root/diagnose-studio/studio/studio.db。
---

# 归档周报：diagnose-studio 归档统计 → 飞书文档

把诊断工作台归档库（SQLite studio.db）的本周会话统计成一份「占比优先」的飞书周报：总体状态占比（饼图 + 占比表）、按人（含结论标记率）、按 skill（含已解决率与「未定位 X · 已优化 Y」）、客户分布、未标记清单、自动化通道单列。

## 执行前必读（缺一不可）

1. [`references/config.md`](references/config.md) — 连接/目标/口径开关（默认值、排除自动化、ID: 归正、是否优化列口径）；
2. [`references/queries.md`](references/queries.md) — SQL 全集与派生指标公式；
3. 组装文档前读 [`references/doc_template.md`](references/doc_template.md) — 章节骨架与 XML 踩坑清单。

## 依赖

- 连接：内部堡垒机（参考 `jumpserver-connect` 的 config；本技能 `scripts/collect_stat.py` 内置 paramiko 交互登录，key `~/.ssh/dyz_inner.jumpserver.pem`，主机搜索词可参数覆盖）。
- 飞书：lark-cli user 身份。执行 `docs +update/+create` 前按 `lark-doc` skill 要求读取 `lark-doc-xml.md` / `lark-doc-style.md` / `lark-doc-update.md`；授权缺失时走 `lark-shared` 的 split-flow（`auth login --no-wait --json` 拿链接二维码 → 用户授权 → 亲自执行 `--device-code`，禁止缓存 device_code）。

## 工作流

### 第 1 步：确认目标与落点（周窗口不用问）
- **周窗口固定规则：每次执行统计窗口 = 本周一 00:00 → 服务器当前时刻（自动计算，含当日最新数据），无需询问日期**；仅当用户显式给出起止日期时才覆盖。
- 统计目标环境/归档库（默认 ta1 的 studio.db，可换内部其他主机）；
- 飞书落点：默认覆盖既有文档（token 见 config.md），用户想新建则 `docs +create`（需确认标题）；用户给新链接则更新那篇；
- 口径开关（排除自动化 mcp、ID: 归正）默认开启，用户可关。

### 第 2 步：现场拉取本周最新快照（硬规则）
```bash
python3 <skill_dir>/scripts/collect_stat.py [--search ...] [--db ...] [--since <可选 YYYY-MM-DD，默认本周一>]
```
- **每次执行必须现场运行本脚本重新拉取最新数据**：脚本自动以本周一 00:00 为起点、覆盖到当前时刻（含当天新增归档与 outcome/修复补标）；**禁止沿用历史对话、旧文档或此前快照文件中的统计数字**。
- 脚本输出开头带服务器时间戳与 0-7 节统计（总数/全量状态/mcp 清单/人工 skill×outcome/人工每人×状态/人工 unresolved+fix/人工未标记/人工 cluster）。
- 用交叉合计自检：人工总数 = 节3合计 = 节4合计 = week_cnt − mcp 数。

### 第 3 步：组装 XML（占比优先样式）
按 `references/doc_template.md` 填入快照，产出 `<cwd>/archive_stat.xml`（用后清理）。要点：
- 状态占比百分比 = 各类/人工总数（保留 1 位）；结论标记率 = (已解决+未定位)/人工总数；
- skill「是否优化」列：`未定位 X · 已优化 Y`，Y 取 unresolved 中 fix_status=optimized 条数（**不是 resolved 数**）；
- mermaid 饼图用 `<whiteboard type="mermaid">`，引号写 `&quot;`；
- 自动化（mcp）会话单列最后一节，不进按人/skill/占比统计。

### 第 4 步：同步飞书
- 覆盖更新：`lark-cli docs +update --doc <token> --command overwrite --content @archive_stat.xml --as user`
- 新建：`lark-cli docs +create --content @archive_stat.xml --as user`（`<title>` 作文档标题）
- 写操作前向用户确认目标文档（更新既有/新建/用户指定链接）与标题。

### 第 5 步：回读校验并清理
`lark-cli docs +fetch --doc <token>` 核对：callout 数字、合计行（按人/skill）、占比表、是否优化 Y、未标记清单行数、`<whiteboard token=...>` 画板存在；删除临时 xml。校验不过则修正后重跑第 4 步。

## 已知坑（务必避免）
- **自动化会话污染**：[mcp]数小智（liuchunwei 账号）的 code-diagnose「【原始问题】」会话来自 MCP 通道（tasks.source='mcp'），全部未标记——不排除会把未标记率与 code-diagnose 指标拉爆；识别用归档 dir_path 前缀匹配 tasks.archive_path + source='mcp'（JOIN 可能放大，仅用于识别 mcp 集合，勿直接按 JOIN 求和）；
- **脏 cluster**：`ID:`（google_ads 归档）须归正 Garena，否则客户分布出现怪值；
- **数据随时在变**：会话新增、outcome/修复补标都实时发生，同一快照内数字必须相互自洽，汇报注明快照时间；
- **outcome 与 fix 是两个维度**：「已解决/未定位/未标记」是 outcome；「是否优化」针对未定位会话的 fix_status=optimized，二者勿混；
- str_replace 对表格/多行不可靠，整篇刷新用 overwrite（此文档为纯统计内容，overwrite 安全）；
- 执行 SQL 的别名：FROM archives 未加别名时不要用 `a.` 前缀。

## References
- [`references/config.md`](references/config.md)
- [`references/queries.md`](references/queries.md)
- [`references/doc_template.md`](references/doc_template.md)

## Scripts
- [`scripts/collect_stat.py`](scripts/collect_stat.py) — 收集一致性快照（需要本机 paramiko）。
