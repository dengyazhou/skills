---
name: dyz-ae-weeklyReport
description: >
  汇总指定对象本周工作并生成飞书周报文档。从四类数据源采集：工单归档目录、
  飞书文档更新记录、git 仓库提交、Codex 会话（可选），归纳为
  【飞书文档更新】【AI 工具建设】【工单记录】【本周主线】四段结构化周报，
  先在对话中展示供用户增删条目，确认后在固定 wiki 目录下写入/更新本周周报文档
  （每周只保留一份）；OKR 进展默认不同步，仅当用户明确要求时按 KR 映射写入。
  数据源、输出目录、KR 映射由本 skill 目录下的 config.json 配置。
  触发词：周报、本周工作、总结本周、工作汇总、weeklyReport、dyz-ae-weeklyReport、ae-weeklyReport、同步到OKR。
agent_created: true
---

# dyz-ae-weeklyReport

把一周散落在多处的工作痕迹（工单、文档、代码提交）汇总成一份周报，
写入飞书云文档；OKR 进展按需追加。

**核心节奏：并行采集 → 展示待确认 → 用户增删 → 生成文档（→ 可选写 OKR）。**

> ⛔ **硬性约束 1：先展示，后同步**
> 采集完成后**必须先在对话中输出完整周报**，等用户确认或增删条目后才写文档。
> 用户常会要求移除若干条飞书文档（那些是顺手打开编辑的参考文档，不算本周产出）。
> 未经确认直接写飞书或 OKR，会产出需要反复覆盖的脏数据。

> ⛔ **硬性约束 2：每周只保留一份周报文档**
> `output.one_doc_per_week=true`。写文档前**必须先查** `output.wiki_parent_node_token` 目录下
> 是否已有本周文档：**有则 `overwrite` 更新，无则新建**，严禁同一周内产出第二份。
> 用户多次让"汇总本周工作"时，后一次应覆盖前一次，而不是新开文档。

> ⛔ **硬性约束 3：OKR 默认不写**
> `okr.auto_sync=false`。汇总只生成飞书文档；只有用户明确说"同步 OKR / 写 OKR"时才执行第五步。

## 第一步（必做）：读取配置与确定周区间

1. 用 `Read` 读取本 skill 目录下的 `config.json`。
2. 计算本周区间：以当前日期所在周的**周一**为 start、**周五**为 end（跨周补录时以用户指定为准）。
3. 记下周一零点的 Unix 时间戳，后续飞书文档过滤要用。

⚠️ **周中执行**（周一~周四）：本周尚未结束，区间 end 取**执行当天**，汇总标题与正文须标注
「截至周X」并在展示时提示用户"本周仍在进行，可周五补全后再同步"，避免把半周数据当整周。

## 第二步：并行采集四类数据源

**必须并行发起**，四个源之间无依赖。逐个串行会让整个流程慢 3-4 倍。

### 1. 工单记录（`sources.tickets`）

```bash
ls -la <tickets.dir>/<周一日期>/
```

再批量抽取标题（文件内首个 `【问题标题】`）：

```bash
cd <tickets.dir>/<周一日期> && for f in 工单记录_*.md; do
  echo -n "${f%.md} :: "; grep -m1 "问题标题" "$f" | sed 's/.*问题标题】\*\*//;s/^ *//'
done
```

工单量通常 15-25 张，**按主题聚合**而非按时间罗列，同一组件/同一类语义问题归到一组
（例如「数据重复与去重」「LogBus 与传输」「三方广告数据拉取」）。

**同时取「工单类型_内容」**（问题排查 / 日常咨询 / 内部需求-问题修复），成文时按类型分组。
一条 MQL 批量查（`work_item_id` 列表从建档时的返回值收集）：

```bash
MQL="SELECT \`name\`, \`field_f91b3e\` FROM \`客户成功\`.\`工单\` WHERE \`work_item_id\` IN (...) LIMIT 30"
meegle workitem query --project-key <project_key> --mql "$MQL"
```

- `project_key` 与工单 skill 共用同一空间，取自 `dyz-ae-ticketRecord/config.json` 的 `feishu_project.project_key`（本 skill 的 config 未单独维护该值）。
- 需 **`meegle` CLI 已安装并登录**（先 `meegle auth status`，详见 `dyz-ae-ticketRecord/SKILL.md`「前置条件」）。
- MQL 用反引号包字段名、单引号包字符串，在 bash 双引号内需转义反引号（`` \` ``）。

返回值取 `data."1"[*].moql_field_list[*].value.key_label_value.label` 即类型文案（如「问题排查」/「日常咨询」）。
也可查本地 md——若文件内已写 `**【工单类型】**` 行则直接读，无需再查飞书。

### 2. 飞书文档更新（`sources.feishu_docs`）

用 `lark-cli docs +search` 空 query 翻页，按 `edit_user_id` 与 `update_time` 过滤。
参考 `references/collect_feishu_docs.py`，或直接内联 python：

```python
args = ["lark-cli","docs","+search","--query","","--as","user","--format","json","--page-size","20"]
# 有 page_token 时追加 --page-token
# 命中条件：m["edit_user_id"] == target.open_id and m["update_time"] >= 周一零点
```

⚠️ **两个坑**：
- 返回结果按 `last_open_time` 排序，**不是** `update_time`。不能因为遇到一条旧文档就 `break`，必须翻满 `max_pages`。
- 数组在 `data.results[]`，翻页标志 `data.has_more`，游标 `data.page_token`。

### 3. git 仓库提交（`sources.git_repos`）

```bash
git log --author="yazhou.TD\|邓亚洲" --since="<周一>" --until="<周五> 23:59:59" \
  --format="%h %ad %s" --date=short
```

需要改动行数时加 `--stat`。多个仓库可在一条命令里用 `&&` 串起来，或并行发起。

⚠️ **`--since`/`--until` 可能静默失效**（实测：`--author` 单独查询正常，叠加 `--since` 后返回空）。
**对策**：先跑不带时间过滤的 `git log -80`，再用 Python 按日期字符串过滤（比 `--since` 稳，也便于统计）：

```python
import subprocess
r = subprocess.run(["git","-C",repo,"log","-80","--format=%h|%ad|%an|%s","--date=short"],
                   capture_output=True, text=True)
rows = [l.split("|",3) for l in r.stdout.splitlines()
        if len(l.split("|",3)) == 4 and l.split("|",3)[1] >= since]   # since='YYYY-MM-DD'
```

**归类原则**：`config.json` 里同 `category` 的仓库在周报中**合并为一个章节**，
下面按仓库分子节。例如 diagnose-studio 与 skills 都属「AI 工具建设」。

⚠️ **本地会话目录可作补充源**：非 `config.json` 登记的工具（如 qa-tool）若本周有实际使用/调试，
可按需从 Reasonix 会话取证补入「AI 工具建设」——读 `~/.reasonix/projects/<项目路径转横线>/sessions/*.jsonl.meta`
的 `topic_title`（会话标题）与 `preview`（首条提问）判断本周做了什么，再按主题归纳。
**只读，勿改会话文件**（应用在跑，外部改动会被存成冲突副本）。

### 4. Codex 会话（`sources.codex_sessions`，默认关闭）

只在配置启用或用户明确要求时采集。噪声很大：大量会话首条 user 消息是
`The following is the Codex agent history...`（reviewer 会话，应跳过），
或被 `# AGENTS.md instructions...</INSTRUCTIONS>` 前缀包裹（需剥离后取真实提问）。
详见 `references/collect_codex_sessions.py`。

## 第三步：成文并展示

按 `output.sections` 顺序组织，每段要求：

| 章节 | 要求 |
|---|---|
| 飞书文档更新 | 表格：更新时间 + 可点击标题链接，倒序 |
| AI 工具建设 | 同 category 的仓库合并；表格：日期 + 内容（+ 改动行数） |
| 工单记录 | **按「工单类型_内容」分两组**：🔍 问题排查 / 💬 日常咨询（含内部需求时单列），组内按主题聚合三列表：主题 / 客户 / 问题 |
| 本周主线 | 2-4 段散文。点出**趋势与关联**，不要复述上面的表格 |

工单分组时给出各组数量（如「问题排查 12 张、日常咨询 8 张」），并在「本周主线」里点出
**类型结构**说明了什么（例：问题排查占比高 = 本周以线上故障处理为主，非答疑）。

「本周主线」是周报的价值所在。好的写法举例：
「新增的 8 张让另外两条线浮出来了：数据重复与去重（尚娱 `#uuid`、拳游 `composit_key`、
海棠 batch 模式，本质都是幂等语义问题）和 LogBus 传输质量（延迟、丢失、卡住，
3 张集中在同一组件）」——把分散工单归纳出共性根因。

展示后主动问：是否要移除某些条目、是否写文档（OKR 默认可不问，用户要求才同步）。

## 第四步：生成/更新周报文档（固定目录，每周一份）

**位置固定**：`output.wiki_parent_node_token` 对应的 wiki 节点（`output.wiki_parent_title`，
即「周总结」）下的子文档。**不要**建在文档库根目录或其它位置。

### 4.1 先查本周是否已有文档（必做）

```
lark-cli wiki +node-list --space-id <output.wiki_space_id> --parent-node-token <output.wiki_parent_node_token> --as user --format json
```

返回 `data.nodes[]`（**注意字段名是 `nodes` 不是 `items`**），每项含 `title` / `node_token` / `obj_token`（**obj_token 才是文档 id**）。
按标题匹配本周区间（`doc_title_template` 渲染结果，如「邓亚洲 本周工作汇总（2026-09-14 ~ 09-17）」；
放宽为包含 start 日期即可）：
- **命中** → 记下该节点 `obj_token`，走 4.3 覆盖更新（同时把正文首行标题改成新区间，即可一并更新文档 title）；
- **未命中** → 走 4.2 新建。

### 4.2 新建节点（本周首次）

```bash
lark-cli wiki +node-create --parent-node-token <output.wiki_parent_node_token> \
  --space-id <output.wiki_space_id> --obj-type docx \
  --title "<渲染后的标题>" --as user --format json
```

返回的 `obj_token` 即文档 id（`node_token` 是 wiki 链接用的 token，两者不同）。

### 4.3 写入正文（新建与更新都用同一套）

**先写本地临时 md，再上传。** 不要把长 markdown 内联到 `--content`。

```bash
cd <cwd> && cat > _weekly.md <<'MD'
# <渲染后的标题>

<周报正文>
MD
# 新建与更新都可直接用 overwrite（新文档为空，等价于写入）
lark-cli docs +update --doc <obj_token> --command overwrite \
  --content @_weekly.md --doc-format markdown --as user --format json
```

> 正文首行 `# 标题` 会合成为文档 title，**不要在正文里重复写标题两遍**；
> 文档标题实际以 4.2 的 `--title` 为准。

⚠️ **已知坑与对策**：
- `@file` 只接受 **cwd 下的相对路径**，绝对路径会报 `unsafe file path`。
- heredoc 与 `--content` 写在同一条命令里容易触发审批审核超时，**分两步执行**：先写文件，再单独跑 lark-cli。
- 中文标题偶发触发审核超时。连续失败 2 次后，用 `output.ascii_title_fallback` 建文档，
  再 `docs +update --command str_replace` 把首行标题改回中文，并用 `docs +fetch` 验证。
- `node-create` 后需用返回的 `obj_token`（不是 `node_token`）去 fetch/update 文档。
- 写完后用 `docs +fetch` 回读校验，并 `wiki +node-get` 确认父节点正确。
- 同步完成后删掉 `_weekly.md`（不留本地临时文件）。

## 第五步：同步 OKR 进展（默认不执行）

> ⛔ `okr.auto_sync=false`：**只有用户明确要求**（如「同步 OKR」「写 OKR」）才走这一步。
> 若本次跳过、用户后来又要求补，直接跑本步即可（OKR 进展独立于周报文档）。

### 5.1 定位当季 KR

`config.json` 的 `kr_mapping` 记录了上季度的 KR id。**换季度后 id 会失效**，需重新获取：

```bash
lark-cli okr +cycle-list --user-id <target.open_id> --as user --format json
# 筛出 start_time/end_time 包含今天的周期，再：
lark-cli okr +cycle-detail --cycle-id <id> --as user --format json
```

拿到新 id 后主动提示用户更新 `config.json`。

**核实是否已同步**：`+progress-list` 的返回数组字段名是 `data.progress_list`（**不是** `progresses`），
若最新一条的内容周次不是本周，说明上周漏写可在下次一并补。查：

```bash
lark-cli okr +progress-list --target-id <kr_id> --target-type key_result --as user --format json -q '.data.progress_list[0]'
```

### 5.2 按映射写进展

每条 KR 单独一次 `+progress-create`，内容用 ContentBlock JSON。
**用 python 生成 json 文件**，不要手写（手写易踩转义坑）：

```python
def para(t): return {'block_element_type':'paragraph','paragraph':{'elements':[{'paragraph_element_type':'textRun','text_run':{'text':t}}]}}
def b(t):    return {'block_element_type':'paragraph','paragraph':{'style':{'list':{'list_type':'bullet','indent_level':0}},'elements':[{'paragraph_element_type':'textRun','text_run':{'text':t}}]}}
link = {'block_element_type':'paragraph','paragraph':{'elements':[{'paragraph_element_type':'docsLink','docs_link':{'url':doc_url,'title':doc_title}}]}}
json.dump({'blocks':[para('...'), b('...'), link]}, open('_okr_x.json','w'), ensure_ascii=False, separators=(',',':'))
```

```bash
lark-cli okr +progress-create --content @_okr_x.json --target-id <kr_id> \
  --target-type key_result --as user --format json -q '.data.progress.progress_id'
```

**每条进展末尾都追加周报文档的 docsLink**，这样 OKR 界面能直接跳转细节。
三条可并行提交。完成后删掉临时 json 并回报 progress_id。

⚠️ `+progress-update` 没有 `--source-url`，链接只能以 docsLink 形式写在内容里。
⚠️ 审批审核器对 `+progress-create` 偶发 JSON 解析报错（`expected , or }`）。
遇到时：去掉 `--source-title` 等可选参数、缩短单条 bullet 文本、改用最小命令重试。
若连续多次失败，把生成好的 json 文件留在 cwd，把命令给用户手动执行，不要反复重试。

## 附：飞书项目数据通道（meegle CLI）

飞书项目相关的查询与写入统一走 **`meegle` CLI**（飞书项目官方 CLI，npm 包 `@lark-project/meegle`），不依赖 MCP。

```bash
meegle auth status    # authenticated 必须为 true；false 时 meegle auth login --device-code
```

| 用途 | 命令 |
|---|---|
| MQL 查工单/客户 | `meegle workitem query --project-key <pk> --mql "<MQL>"` |
| 回读字段 | `meegle workitem get --project-key <pk> --work-item-id <id> --fields _all` |
| 建单 / 改字段 | `meegle workitem create` / `meegle workitem update` |
| 排期 + 估分 | `meegle workflow update-node --node-schedule '{...clear_schedule...}'` |
| 回读排期/估分 | `meegle workflow get-node --node-id-list <state_id>` |
| 按视图拉工作项 | `meegle view get --view-id <id> --project-key <pk>` |
| 解析飞书项目链接 | `meegle url decode --url <URL>`（得 `view_id` / `work_item_id` 等结构化字段） |

**排期校验**：`workflow get-node` 返回的 `schedule.estimate_start_time` / `estimate_finish_time` / `points` 即实际排期与估分。

**两条写入约定（方向相反，勿混用）**：
- `--fields` 的 `field_value` 是**字符串协议**——数字也要加引号（`"214223"`），数组/对象需 JSON.stringify；
- `workflow update-node` 的 `--node-schedule` 是**原生 JSON**——`points` 必须是数字（传 `"0.1"` 报 `must be number, got string`）。

各命令的完整用法与字段分类规则见 `dyz-ae-ticketRecord/SKILL.md`「同步到飞书项目」章节。

## 常见坑

| 现象 | 原因 | 对策 |
|---|---|---|
| 飞书文档少了几份 | 提前 break，误以为按 update_time 排序 | 翻满 max_pages |
| 工单数量与上次不符 | 用户在周五下午补录了工单 | 每次重新 `ls`，不复用历史结论 |
| `git log --author` 空结果 | 只匹配了一种署名 | 用 `"yazhou.TD\|邓亚洲"` |
| `git log --since` 也空 | 时间过滤静默失效 | 去掉 `--since`，用 Python 按 `%ad` 字符串过滤 |
| 同一周出现两份周报文档 | 写前没查重 | 先 `wiki +node-list` 查，有则 overwrite |
| 文档建错位置 | 用了 `docs +create` 而非 wiki 建节点 | 走 `wiki +node-create --parent-node-token` |
| 用 node_token 去 fetch 报错 | node_token ≠ 文档 obj_token | 用返回的 `obj_token` |
| 审批审核超时 | 命令过长或含中文长标题 | 拆分命令、ASCII 标题兜底 |
| OKR 写错 KR | 沿用了上季度 kr_id | 每季度首次执行先 `+cycle-detail` 核对 |
| `+progress-list` 读不到 | 字段名记错 | 用 `.data.progress_list` |
| `meegle` 报未登录 / 认证失败 | access token 约 2h 过期 | `meegle auth login --device-code`（refresh_token 通常自动续期，正常无需手登） |
| `field_value` 传数字被拒 | 协议层固定字符串 | 数字也加引号，如 `"214223"` |
| 周中执行却写整周 | 区间取到周五 | end 取当天并标注「截至周X」 |

## 不在本 skill 范围

- 工单本身的归纳生成 → 用 `dyz-ae-ticketRecord`
- OKR 撰写、双周复盘、对齐检查 → 用 `okr-agent`
