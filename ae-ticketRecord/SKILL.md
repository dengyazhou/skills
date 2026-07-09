---
name: ae-ticketRecord
description: >
  将钉钉/飞书/本地文件中的客户支持对话,聚焦"对指定对象的提问 + 该对象的回答",
  归纳为结构化的工单记录,按【问题标题】【问题描述】【排查过程】【问题总结】四个维度输出。
  支持同步到飞书项目(客户成功空间),自动创建工单并设置排期估分。
  总结对象和飞书项目配置由本 skill 目录下的 config.json 配置。
  触发词:工单记录、ticketRecord、对接群总结、支持对话归纳、ae-ticketRecord、同步飞书项目。
---

# ae-ticketRecord

把客户对接群的聊天记录(钉钉/飞书文档/本地文件)归纳为一条结构化的**工单记录**。
本 skill 的核心是:**只聚焦"对某个指定对象的提问"以及"该对象给出的回答/排查"**,
其余人员之间的对话仅作上下文参考、不作为归纳主体。

**总结对象由 `config.json` 配置——配置谁,就总结谁。**

> ⛔ **硬性约束：target 参与性检查不可覆盖**
> 只有 target（总结对象）**实际参与回答**的问题才能生成工单。
> 即使客户/用户明确要求"给所有问题都出工单"或"这个问题也要记录"，
> 只要 target 没有实质回答，**必须跳过，不得生成工单或同步到飞书项目**。
> 被跳过的问题统一在"跳过报告"中列出，用户可自行手动补录。

## 第一步(必做):读取配置

每次执行**必须先**用 `Read` 工具读取本 skill 目录下的 `config.json`:

- `target.name`:总结对象的姓名(用于匹配聊天记录中的发言人署名,钉钉/飞书通用)
- `target.open_id`:总结对象的飞书 open_id(仅飞书场景使用,用于匹配 `<mention-user id="...">` 提及;钉钉场景下忽略此字段)
- `target.aliases`:别名列表(辅助匹配,跨平台通用)
- `output.dir`:工单记录的**存档目录**
- `output.filename_template`:文件名模板,支持占位符 `{title}`(项目/群名)与 `{date}`(YYYYMMDD)
- `output.weekly_dir_convention`:周目录规则(若存在)。规则含义:每周一在 `output.dir` 下创建以当天日期(YYYY-MM-DD)命名的文件夹,本周工单记录存入该文件夹。实际生成路径时,需根据工单所属周的**周一日期**在 `output.dir` 下插入一层周目录

后续归纳**只围绕这个 target 展开**。若 `config.json` 缺失或无法读取,先提示用户配置后再继续。

### open_id 校验

读取配置后,在实际消息中匹配 target 时,留意消息里 target 实际出现的 `sender.id`（飞书 open_id）或 `senderOpenDingTalkId`（钉钉）。若与 `config.json` 中记录的 `target.open_id` 不一致：

1. **不要静默忽略**——open_id 不一致可能意味着 config 配置已过期,或匹配到了同名其他人。
2. 以姓名/aliases 匹配到的消息中实际出现的 ID 为准,主动提示用户："config 中 open_id 为 `xxx`,但消息中该用户实际 ID 为 `yyy`,是否更新 config？"
3. 用户确认后,用 `Edit` 工具更新 `config.json` 中的 `target.open_id`。

此校验可避免因 open_id 过期导致 target 消息漏匹配。

## 输入源

输入可以是以下任意一种,从用户消息中识别或向用户确认:

- **钉钉私聊/群聊**:用户指定"拉取钉钉和 XX 的消息"或"钉钉聊天记录"。先通过 `dws contact user search --keyword "姓名"` 获取目标用户的 `openDingTalkId`,再用 `dws chat message list-direct --open-dingtalk-id <id> --time "起始时间" --forward true --limit 100` 拉取私聊记录;群聊则用 `dws chat search --query "群名"` 找到 `openConversationId` 后,用 `dws chat message list --group <id>` 拉取。
- **飞书文档**:文档标题或 URL(如 `https://thinkingdata.feishu.cn/wiki/xxxx`)
- **本地文件**:`.md`、`.txt`、`.docx`、`.pdf` 等路径
- **目录**:扫描目录下的相关文件
- **多个文档**:一次传入多个飞书 URL(用「、」、逗号或换行分隔)或多个文件路径,需逐个读取后按下方"多文档处理"规则归纳

## 多文档处理(合并 vs 拆分)

一次给到多个文档时:

1. 逐个 `fetch-doc` / `Read` 读取全部内容。
2. 判断这些文档是否同属一件事:
   - **同一任务/同一问题链**(如多个群在推进同一个评估、同一个故障的不同现场)→ **合并为一条工单**;在【排查过程】各步骤后用括注标明来源(如"(内部群)""(与某某会话)"),还原跨群协作脉络。
   - **互不相关的独立问题** → **各自出独立工单**,分别按模板成文与存档。
3. 拿不准是否相关时,先问用户要"合并成一条"还是"分开成多条"。
4. **合并工单的命名**:`{title}` 取能概括整件事的名称(如"天梯夜幕之下项目LogBus容量评估"),而非其中某个单一群名。

## 读取方式

- **钉钉私聊/群聊**:使用 `dws chat` 系列命令直接拉取 JSON 格式消息(无需手动解析文档)。命令返回的每条消息已包含 `sender`(发言人姓名)、`senderOpenDingTalkId`、`content`(文本内容,图片/文件为占位说明)、`createTime`(时间)。拉取后直接按 JSON 字段匹配 target,无需正则或 HTML 解析。
- 飞书文档:若用户给了 URL 可直接传入 `mcp__feishu-mcp-dyz__fetch-doc`;若只给标题,先用 `mcp__feishu-mcp-dyz__search-doc` 搜到 `doc_id` 再 `fetch-doc`。
- 本地纯文本文件(`.md`、`.txt`等):用 `Read` 工具读取。
- 聊天记录中的图片(image token)通常是辅助截图,可不展开;如内容关键且用户要求,再用 `mcp__feishu-mcp-dyz__fetch-file` 取图分析。钉钉消息中的图片显示为 `[图片消息](mediaId=@xxx)`,文件显示为 `[文件] xxx`,内容不可直接读取,仅作为上下文参考。

### docx 文件双路径提取

飞书/企业微信导出的 `.docx` 文件，聊天数据可能存储在两处:

1. **标准路径**: `textutil -convert txt -stdout <file>` 提取 `<w:t>` 标签文本。
2. **自定义元素路径**: 若标准路径只拿到标题/占位文本(如"群聊的聊天记录")，说明聊天数据在 `WXWORK_GROUP_CHAT` 自定义 XML 元素中，需走以下流程:

```
a. 解压 docx: unzip -o <file> -d /tmp/extract/
b. 读取 word/document.xml，用正则 WXWORK_GROUP_CHAT 定位所有 JSON 块
   ⚠️ 重要: 文件中可能有多个独立的 WXWORK_GROUP_CHAT JSON 块（每块是一段聊天片段），
   必须逐一提取所有块，而非只取第一个。
c. 对每个匹配位置: 从该位置后的 { 开始，按花括号深度匹配提取完整 JSON，
   html.unescape 反转义 &quot; 等实体，json.loads 解析
d. 将所有块的 jsonData.chatList 合并，按 timestamp 升序排序，
   得到完整聊天记录（username / timestamp / textContent）
e. 验证: 输出总消息数，如明显偏少（如 < 10 条但文件体积较大），需重新检查是否漏提取
```

**关键**: 必须先尝试标准路径，结果异常(内容过少、无实际对话)时自动切换到自定义元素路径，不可只试一种就放弃。自定义元素路径必须提取**所有** `WXWORK_GROUP_CHAT` 块，漏块会导致对话不完整。

## 识别"对 target 的提问"与"target 的回答"

根据输入源类型,判定逻辑略有不同:

### 钉钉 (dws chat JSON)

钉钉数据已结构化,每条消息包含 `sender`(姓名)、`senderOpenDingTalkId`、`content`(文本)、`createTime`:

1. **对 target 的提问**:满足任一条件即算
   - 消息的 `sender` != `target.name`(也非 aliases),且消息内容中含有 target 的姓名或别名(如 "亚洲 项目组最近反馈...");
   - 消息 `sender` 不是 target,但根据上下文是在向 target 求助/提问,且**下一条的 `sender` 为 target**。
2. **target 的回答**:`sender` 匹配 `target.name` 或 `target.aliases` 中任一项的消息。
3. 其他人(如另一位支持同事)的发言:仅作上下文,不计入归纳主体;如其转达了客户诉求给 target,可并入对应问题的描述。

### 飞书 / 本地文本

按聊天记录的发言人署名(正文里形如 `<text color="gray">姓名 日期 时间</text>`)和 `<mention-user>` 提及来判定:

1. **对 target 的提问**:满足任一条件即算
   - 消息中 `@` 了 target(`<mention-user id="{target.open_id}">`);
   - 消息虽未显式 @,但根据上下文是在向 target 求助/提问,且**下一条由 target 作答**。
2. **target 的回答**:发言人署名为 `target.name`(或命中 aliases)的消息。
3. 其他人(如另一位支持同事)的发言:仅作上下文,不计入归纳主体;如其转达了客户诉求给 target,可并入对应问题的描述。

## 归纳规则

1. **只归纳 target 相关的问答主线**,不逐句复述无关闲聊。
2. **多个问题合并为一条工单**:涉及多个相关小问题时,**问题标题提炼为一个**概括全局的标题;各小问题在【问题描述】里编号列出,在【排查过程】里按编号对应展开 target 的处理。
3. **排查过程不出现 target 的姓名**:只描述"做了什么、怎么解决"(客户提问方姓名可保留以还原上下文)。
4. **区分根因**:在【问题总结】里点明问题是产品/SDK 缺陷,还是客户自身配置/业务逻辑问题。
5. **保留关键技术细节**:接口名、属性名、API(如 `getSuperProperties`)、配置项、文档指引等照实保留。
6. **【问题描述】仅记录客户主动向 target 提出的诉求与疑问**:target 自行排查中发现的关联问题(如排查项目A时顺带发现项目B也有问题),应归入【排查过程】而非【问题描述】。判定标准:该问题是否由客户方(非 target、非内部同事)的消息首先提出。
7. **根因等关键结论必须溯源到原文**:归纳中的每一条关键判断(尤其是根因定位——是产品缺陷还是客户侧问题)必须能在聊天记录中找到对应的原始消息作为依据。若原文说的是"客户未操作某步骤",不可写成"系统未正确执行某步骤";若原文没有体现产品缺陷,不可自行定性为产品缺陷。结论必须忠实于原文表述,不可凭表面印象推断或拔高。
8. **不添油加醋——只归纳消息中实际出现的内容**:工单中的每一条技术细节(API名、配置项、修复方案、代码片段等)必须在聊天记录中有对应的原始消息。禁止凭空补充聊天中未出现的细节——即使推测合理也不可编造。若群内只说"修复了SQLite多线程并发问题",不可自行补充"通过串行队列+FULLMUTEX修复";除非这些细节确实在某条消息中被明确写出。
9. **区分消息来源与发言归属**:Bot/系统消息(如TQA机器人)中展示的内容,其实际作者以消息内标注的提出人/撰写人为准,而非 bot 本身。例如 TQA bot 发出的工单内容中标注"提出人:张三",则其中内容归因于张三。此外,同一个技术细节(如优化建议)在初始工单描述中出现过、但在后续排查群聊中未被相关开发人员复述时,不可将此细节归因于该开发人员——必须忠实于每条消息的实际 speaker 和内容。

## 输出格式

```
# <项目名/群名> 工单记录

**【问题标题】** <一个概括全局的标题>

**【问题描述】**
<客户向 target 提出的诉求与疑问。多个问题时编号列出>

**【排查过程】**
<target 的解答与排查动作,与问题描述编号对应、按步骤展开;
保留关键接口/属性/文档指引;不出现 target 姓名>

**【问题总结】**
<结论性归纳:方案是否可行、关键约束、根因定位(缺陷 or 客户侧问题)、最终是否闭环>
```

## 同步到飞书项目

当用户要求"同步到飞书项目"或 `config.json` 中 `feishu_project.enabled = true` 且用户未明确跳过同步时,执行以下流程。**同步前必须先完成本地文件的生成,以本地文件内容为准。**

### 前置条件

需飞书项目 MCP 已连接（`mcp__FeishuProjectMcp__*` 系列工具可用），且拥有对目标空间的读写权限。

### 同步步骤

#### 1. 读取配置与工单内容

读取 `config.json` 获取 `feishu_project` 配置,同时读取已生成的本地工单文件,提取四个维度内容:
- **问题标题** → 飞书项目工单 `name`
- **问题描述** → `field_d42436`（起因说明）
- **排查过程** → `field_d264eb`（排查过程）
- **问题总结** → `field_80a262`（问题总结）

#### 2. 查找客户

用 MQL 在飞书项目中搜索客户:

```
mcp__FeishuProjectMcp__search_by_mql
  project_key: <feishu_project.project_key>
  mql: SELECT `name`, `work_item_id` FROM `<project_key>`.`客户` WHERE `name` LIKE '%<客户名称>%' LIMIT 5
```

从结果中匹配客户名称,获取 `customer_work_item_id`。若搜索无结果或名称不匹配,询问用户确认客户名称或手动提供客户 ID。

#### 3. 组装工单名称

按 `naming.format` 模板组装工单名称。若模板中包含 `{customer_short_name}`，则从飞书项目客户名称中提取简称：

- **提取规则**：取客户名称中**第一个中文括号内的文本**，如 `（呸喽）广州呸喽呸喽科技有限公司` → `呸喽`。
- **兜底**：若名称中无括号，则使用完整客户名称。

若模板中使用的是 `{customer_name}`，则直接使用飞书项目中的完整客户名称。

#### 4. 创建工单

```
mcp__FeishuProjectMcp__create_workitem
  project_key: <feishu_project.project_key>
  work_item_type: <feishu_project.work_item_type>
  fields:
    - field_key: "name" → 组装后的工单名称
    - field_key: <field_mapping.customer_id> → 客户 work_item_id
    - field_key: <field_mapping.customer_name> → 客户名称文本
    - field_key: <field_mapping.问题描述> → 【问题描述】内容
    - field_key: <field_mapping.排查过程> → 【排查过程】内容
    - field_key: <field_mapping.问题总结> → 【问题总结】内容
    - 合并 defaults.field_values 中的全部默认值
```

#### 5. 设置排期与估分

创建成功后,用 `update_node` 设置默认排期和估分。**必须传 `clear_schedule: true`**,否则排期日期不会生效：

```
mcp__FeishuProjectMcp__update_node
  project_key: <feishu_project.project_key>
  work_item_id: <创建返回的 id>
  node_id: <feishu_project.schedule_node_id>
  node_schedule:
    clear_schedule: true
    points: <defaults.points>
    estimate_start_date: <当天 00:00:00 毫秒时间戳>
    estimate_end_date: <当天 23:59:59 毫秒时间戳>
    owners: ["<当前用户 open_id>"]
```

时间戳计算方式（北京时间 CST, UTC+8）:
```python
from datetime import datetime, timezone, timedelta
cst = timezone(timedelta(hours=8))
start = datetime(2026, 6, 24, 0, 0, 0, tzinfo=cst)
end = datetime(2026, 6, 24, 23, 59, 59, tzinfo=cst)
start_ms = int(start.timestamp() * 1000)   # 当天起始
end_ms = int(end.timestamp() * 1000)       # 当天结束
```

#### 6. 验证同步结果

用 `get_workitem_brief` 或 `search_by_mql` 回读确认工单名称、排期、估分已正确写入。若字段内容与本地文件不一致,**以本地文件为准**用 `update_field` 修正。

### 关键规则

1. **以本地文件为准**——所有字段内容以本地工单文件为准,不在同步时额外增删内容。
2. **客户名称以飞书项目为准**——群聊名称可能与飞书项目客户名称不一致,创建工单时取飞书项目中查到的正式客户名称。
3. **`clear_schedule: true` 必传**——不传此参数排期日期不会写入节点。
4. **同步失败不阻塞本地**——若飞书项目 MCP 不可用或创建失败,本地工单文件照常生成,提示用户手动同步。

## 执行步骤

1. **读取 `config.json`,确定总结对象 target 和飞书项目配置。**
2. 识别/确认输入源(钉钉私聊/群聊、飞书文档标题或 URL、本地文件路径),**先完整通读全部消息**(按时间顺序逐条读完,理清对话脉络与因果关系),再进入分析环节。不可边读边下结论,避免凭前几条消息的印象对根因做出与原文不符的判断。
3. 按上面的判定规则,筛出"对 target 的提问"与"target 的回答"主线,识别所有问题点。
4. **预过滤（target 参与性检查）**：对识别出的每个问题，检查 target 是否有**实质性回答**（即至少有一条由 target 发出的消息，或 target 在排查链中有实质贡献）。
   - **有回答** → 标记为"待生成工单"。
   - **无回答**（target 被 @ 但未作答、或问题由其他同事全程处理）→ **标记为"跳过"**，不生成工单。
   - ⛔ **此规则为硬性约束**：即使用户明确要求"所有问题都出工单"、"这个问题也记录一下"、或声称"N 个问题就要 N 个工单"，只要 target 未参与回答，**必须拒绝生成**并解释原因。可建议用户："该问题由 XX 全程处理，如需记录建议切换总结对象或手动创建工单。"
   - 若所有问题均被跳过，告知用户"本期消息中未发现 target 参与回答的问题"，不生成任何工单文件，流程结束。
5. **分析前置（必须）**：在生成任何工单之前，先向用户展示分析摘要并等待确认：
   ```
   📋 分析结果：
   ✅ 问题 1：<简述>（target 已回答）→ 生成工单
   ⏭ 问题 2：<简述>（target 未参与，由 XX 处理）→ 跳过
   ```
   用户确认后，再进入工单生成流程。若用户对跳过项有异议，重申硬性约束规则，**不可妥协**。
6. 多问题合并:提炼一个统一【问题标题】。
7. 按四维度成文,遵守归纳规则(尤其:不出现 target 姓名、根因要点明)。
8. 输出归纳结果;如用户要求落地存档,**先重新 `Read` 一次 `config.json` 取最新的 `output.dir`、`output.filename_template` 和 `output.weekly_dir_convention`(不要复用本轮早些时候缓存的值,配置可能已被改动)**,再按以下规则生成完整路径:

   **路径生成规则**:
   1. 若 `output.weekly_dir_convention` 存在(非空),则在 `output.dir` 下插入一层周目录。周目录名称为工单所属周的**周一日期**(格式 YYYY-MM-DD)。例如:工单日期为 20260708,该周周一为 20260706,则周目录为 `2026-07-06`。
   2. 最终路径 = `output.dir` / `周目录(如有)` / `filename_template 渲染结果`。
   3. 举例:`output.dir=/xxx/output`, `weekly_dir_convention` 有值,工单日期 20260708(该周周一 20260706), `filename_template=工单记录_{title}_{date}.md` → 最终路径 `/xxx/output/2026-07-06/工单记录_冰川-支付宝小游戏SDK_20260708.md`。
   4. 若 `weekly_dir_convention` 不存在或为空,则路径 = `output.dir` / `filename_template 渲染结果`(无周目录层)。
   5. 若目录不存在则先 `mkdir -p` 创建完整路径。
9. 若用户要求同步到飞书项目（或 `feishu_project.enabled` 且未跳过）,按「同步到飞书项目」章节执行。
10. **输出跳过报告**：若步骤 4 中有问题被跳过（target 未参与回答），在所有工单生成完毕后，追加一段摘要告知用户哪些内容未生成工单：

```
⏭ 已跳过（target 未参与回答）：
- 问题简述 A
- 问题简述 B
```

此报告让用户知晓哪些群内讨论未被记录，便于后续按需补录或转交其他同事处理。
