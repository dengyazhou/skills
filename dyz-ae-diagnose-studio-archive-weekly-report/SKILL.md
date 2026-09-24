---
name: dyz-ae-diagnose-studio-archive-weekly-report
description: 汇总 diagnose-studio（数据排查工作台 Web Studio）部署上的本周归档统计，生成「占比优先」样式的飞书云文档并同步。当用户需要查看 diagnose-studio / 数据排查工作台的历史归档统计（本周多少个会话、每人多少、已解决/未定位/未标记占比、按 skill/客户分布、未定位优化状态、批量导入单列），或要把该统计同步/刷新到飞书文档时使用。统计口径含网页端（web）与 MCP 通道（[mcp]数小智）发起的用户会话，排除批量导入的历史归档与默认排除的 owner（liuchunwei）。也承接「重新拉一下数据同步飞书」「归档统计周报」「看下已解决/未定位占比」等说法。默认数据源：内部堡垒机 jumpserver-inner-v4 上 ta1（运维-技术交付测试机-腾讯云-刘路）的 /root/diagnose-studio/studio/studio.db。
---

# 归档周报：diagnose-studio 归档统计 → 飞书文档

把诊断工作台归档库（SQLite studio.db）的本周会话统计成一份「占比优先」的飞书周报：总体状态占比（饼图 + 占比表）、按人（含结论标记率）、按 skill（含已解决率与「未定位 X · 已优化 Y」）、客户分布、未标记清单、批量导入单列。统计口径含网页端与 MCP 通道的用户会话；`scan-import` 批量导入的历史归档单列不计入，指定 owner（默认 liuchunwei）的会话也默认排除。

## 执行前必读（缺一不可）

1. [`references/config.md`](references/config.md) — 连接/目标/口径开关（默认值、排除自动化、ID: 归正、是否优化列口径）；
2. [`references/queries.md`](references/queries.md) — SQL 全集与派生指标公式；
3. 组装文档前读 [`references/doc_template.md`](references/doc_template.md) — 章节骨架与 XML 踩坑清单。

## 依赖

- 连接：内部堡垒机（参考 `dyz-ae-jumpserver-connect` 的 config；本技能 `scripts/collect_stat.py` 内置 paramiko 交互登录，key `~/.ssh/dyz_inner.jumpserver.pem`，主机搜索词可参数覆盖）。
- 飞书：lark-cli user 身份。执行 `docs +update/+create` 前按 `lark-doc` skill 要求读取 `lark-doc-xml.md` / `lark-doc-style.md` / `lark-doc-update.md`；授权缺失时走 `lark-shared` 的 split-flow（`auth login --no-wait --json` 拿链接二维码 → 用户授权 → 亲自执行 `--device-code`，禁止缓存 device_code）。

## 工作流

### 第 1 步：确认目标与落点（周窗口不用问）
- **周窗口固定规则：每次执行统计窗口 = 本周一 00:00 → 服务器当前时刻（自动计算，含当日最新数据），无需询问日期**；仅当用户显式给出起止日期时才覆盖。
- 统计目标环境/归档库（默认 ta1 的 studio.db，可换内部其他主机）；
- **飞书落点（按周隔离，硬规则）：每次执行为当前统计周新建一篇独立飞书文档（标题带周日期，如《diagnose-studio 本周归档统计 2026-09-14》），绝不覆盖历史周的文档**；仅当用户显式给出某篇 docx token/链接要求原地更新时才覆盖该篇。
- 口径开关默认开启：**统计口径 = 排除 `archives.source='scan-import'` + 排除 `liuchunwei`（其会话为 MCP 通道测试/占位内容，不代表真实排查）**——`web` 与 `mcp` 来源**均计入统计**（MCP 通道发起的也是用户真实会话）；批量导入单列末节、liuchunwei 只在口径注明一句，均不进统计；`cluster` 脏值 `ID:` 归正 Garena。

### 第 2 步：现场拉取本周最新快照（硬规则）
```bash
python3 <skill_dir>/scripts/collect_stat.py [--search ...] [--db ...] [--since <可选 YYYY-MM-DD，默认本周一>] [--exclude-owner liuchunwei]
```
- **每次执行必须现场运行本脚本重新拉取最新数据**：脚本自动以本周一 00:00 为起点、覆盖到当前时刻（含当天新增归档与 outcome/修复补标）；**禁止沿用历史对话、旧文档或此前快照文件中的统计数字**。
- 脚本输出开头带服务器时间戳与 0-10 节统计（总数/本周来源分布/全量状态/统计口径 skill×outcome/统计口径 每人×状态/统计口径 unresolved+fix/统计口径 未标记/统计口径 cluster/MCP 与 web 来源明细/scan-import 单列/已排除 owner 单列）。
- 用交叉合计自检：**统计口径 + scan-import + 已排除 owner = week_cnt**，且 统计口径 = web 条数 + mcp 条数（看第 1 节「本周来源分布」、第 8/8c 节、第 9/10 节）。

### 第 3 步：组装 XML（占比优先样式）
按 `references/doc_template.md` 填入快照，产出 `<cwd>/archive_stat.xml`（用后清理）。要点：
- 状态占比百分比 = 各类/统计总数（保留 1 位）；结论标记率 = (已解决+未定位)/统计总数；
- skill「是否优化」列：`未定位 X · 已优化 Y`，Y 取 unresolved 中 fix_status=optimized 条数（**不是 resolved 数**）；
- mermaid 饼图用 `<whiteboard type="mermaid">`，引号写 `&quot;`；**饼图禁写 0 值扇区**（如「未定位 0」）——否则 lark 报 `degrade_code=2107` 并丢弃整个画板，只列非零状态；
- 按人表不含被排除的 owner（liuchunwei）与批量导入；可加一行说明来源构成（如「网页端 35 条 + MCP 通道 24 条」）；
- 末尾单列一节：**批量导入历史归档（scan-import）**；不进按人/skill/占比统计，条数多时按「skill × 状态」汇总 + 时间范围呈现。

### 第 4 步：同步飞书（默认新建周文档，落在归档 wiki 目录下）
- **默认动作：`lark-cli docs +create --parent-token EGqlwLYG9ihxnGkVd6UcuEphnob --content @archive_stat.xml --as user`**——为本周新建独立文档并直接挂在 wiki 节点《每周diagnose-studio归档统计》下（`<title>` 作文档标题，标题内日期即统计周的周一）；创建成功后把新 URL 交给用户并登记到 references/config.md 的周文档清单。
  - 该 `--parent-token` 即 config.md「飞书目录（wiki 父节点）」的 node_token；**周文档必须建在此目录下**（用户明确要求）。
  - 若文档已误建在云空间根目录，用 `lark-cli wiki +move --obj-type docx --obj-token <doc_token> --target-space-id 7314274064414457859 --target-parent-token EGqlwLYG9ihxnGkVd6UcuEphnob --as user` 迁入（docx token 与内容不变，返回新的 wiki node_token）。
- 仅当用户显式要求更新某篇已有 docx（给出 token/链接，如“更新到 DUiR…这篇”）时才执行 `docs +update --doc <token> --command overwrite --content @archive_stat.xml --as user`；
- 同一周内重复执行且用户要求原地刷新时，可覆盖该周自己的文档；**跨周一律新建，禁止覆盖其他周的文档**。

### 第 5 步：回读校验并清理
`lark-cli docs +fetch --doc <token>` 核对：callout 数字、合计行（按人/skill）、占比表、是否优化 Y、未标记清单行数、`<whiteboard token=...>` 画板存在。**注意 create/update 返回里的 `warnings`：若出现 `degrade_code=2107`（画板解析失败）须按 doc_template 的「二、」补插步骤单独补画板**。删除临时 xml。校验不过则修正后重跑第 4 步。

## 已知坑（务必避免）
- **批量导入污染（务必排除）**：`archives.source='scan-import'` 是归档目录扫描入库的**历史归档**（`created_at` 为导入时刻而非原始排查时刻，会一次性灌入大量旧问题，如 2026-09-14 17:15:19 一次性 81 条、内容跨 2026-07~08）。不排除会把本周总量、人均工作量、未标记率全部打爆；必须排除并单列末节；
- **MCP 不是「非人工」（易错）**：`tasks.source='mcp'`（[mcp]数小智 通道）发起的会话**也是用户真实使用，要计入统计**（用户明确要求，2026-09-16 确认）。别把它当自动化噪音剔掉；其 owner 也不固定（liuchunwei/dengyazhou/zhangshengwen 等都有）。识别用归档 dir_path 前缀匹配 tasks.archive_path + source='mcp'（JOIN 可能放大，仅用于识别集合与来源对照，勿直接按 JOIN 求和）；脚本第 8/8c 节给出 MCP/web 来源明细可核对；
- **liuchunwei 默认排除（用户要求，长期生效）**：该 owner 的会话均为 MCP 通道测试/占位内容（`【原始问题】`/`__SKIP__`/`完全无关的问题 xyz`），不代表真实排查，故从统计口径排除；脚本 `--exclude-owner` 默认 `liuchunwei`，其会话在第 10 节单列便于核对；**文档只在「统计口径」注明一句「已排除 liuchunwei 的 N 条」，不列明细**；
- **脏 cluster**：`ID:`（google_ads 归档）须归正 Garena；另见 `优化`/`使用`/`TE`/`App` 等由问题文本误提取的值，如实呈现并可在注中提示；
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
