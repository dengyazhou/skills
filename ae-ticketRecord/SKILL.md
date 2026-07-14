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

- **钉钉私聊/群聊**:用户指定"拉取钉钉和 XX 的消息"或"钉钉聊天记录"。先通过 `dws contact user search --query "姓名"` 找人(参数是 `--query`,不是 `--keyword`),从结果里取 `userId` 或 `openDingTalkId`;再用 `dws chat message list` 拉取单聊:`dws chat message list --open-dingtalk-id <openDingTalkId> --time "起始时间" --direction newer --limit 100`(有 `userId` 时也可用 `--user <userId>`,二选一)。群聊则用 `dws chat search --query "群名"` 找到 `openConversationId` 后,用 `dws chat message list --group <id> --time "起始时间" --direction newer` 拉取。**注意:没有 `list-direct` 子命令、也没有 `--forward` 参数;单聊/群聊统一走 `message list`,时间方向用 `--direction newer|older`。**
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

- **钉钉私聊/群聊**:使用 `dws chat` 系列命令直接拉取 JSON 格式消息(无需手动解析文档)。命令返回的每条消息已包含 `sender`(发言人姓名)、`senderOpenDingTalkId`、`content`(文本内容,图片/文件为占位说明)、`createTime`(时间);消息数组在返回体的 `result.messages[]`,翻页标志是 `result.hasMore`。拉取后直接按 JSON 字段匹配 target,无需正则或 HTML 解析。
  - **找人拿到的 ID 优先级**:`dws contact user search` / `dws aisearch person` 对跨组织或外部联系人常常只返回 `openDingTalkId`、`userId` 为 null。此时**直接用 `--open-dingtalk-id` 拉单聊**,不要因为 `userId` 为空就卡住。参见下文"常见坑"中的"跨组织单聊 ID 不通用"。
- **飞书群聊/私聊**:用 `lark-cli im`（实际命令以环境为准）拉取 JSON 消息。**一步到位、避免重复拉取**:
  1. 按群名搜 chat_id:`lark-cli im +chat-search --query "群名" --as user`。**用最短的唯一关键词**(如「视波」「天天玩家」)命中最快;传完整全称反而更慢、也更易 miss。
  2. 按天拉消息(一次带全参数,不要先拉一遍再补拉):
     `lark-cli im +chat-messages-list --chat-id "oc_xxx" --start "YYYY-MM-DDT00:00:00+08:00" --end "YYYY-MM-DDT23:59:59+08:00" --order asc --page-size 50 --no-reactions --as user`
     - 时间用 **ISO 8601**(`--start`/`--end`),不是秒/毫秒时间戳;排序 flag 是 `--order asc`。
     - **默认加 `--no-reactions`**:reactions 富集会明显变慢,归纳工单用不到。需要展示可直接用 `jq`/管道把 `sender.name` + `content` + `create_time` 打平输出,不必二次调用。消息数组在返回体的 `data.messages[]`(不是 `items`),翻页标志是 `data.has_more`;打平前先定位到 `data.messages`。
     - `has_more:true` 时才翻页(`--page-token`),否则一页 50 条即全量。
  3. 消息里 target 的匹配:飞书发言人在 `sender.id`(open_id)、被 @ 在 `mentions[].id`,与 `config.json` 的 `target.open_id` 直接比对。
  4. 若 `+messages-search`(跨群搜消息)报 `missing_scope: search:message`,说明缺该 scope,**不要反复重试**;改用 `+chat-search` 按群名定位,或让用户给 chat_id/链接。
- 飞书文档:优先用当前环境已启用的飞书文档能力读取。若存在 `fetch-doc`/`search-doc` 一类 MCP 工具（如 `mcp__feishu-mcp-dyz__fetch-doc`），给了 URL 直接 `fetch-doc`,只给标题先 `search-doc` 拿 `doc_id` 再 `fetch-doc`；若这类工具不可用,则改用 `lark-doc` skill（给 URL/token 读正文）或 `lark-wiki`/`lark-drive`（先按标题定位 token）。**工具名/前缀以当前环境实际暴露的为准,不要照抄。**
- 本地纯文本文件(`.md`、`.txt`等):用 `Read` 工具读取。
- 聊天记录中的图片(image token)通常是辅助截图,可不展开;如内容关键且用户要求,再用环境中可用的取图工具(如 `mcp__feishu-mcp-dyz__fetch-file`,或对应 skill 的图片读取能力)取图分析。钉钉消息中的图片显示为 `[图片消息](mediaId=@xxx)`,文件显示为 `[文件] xxx`,内容不可直接读取,仅作为上下文参考。

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

需飞书项目 MCP 已连接（工单查询/创建/更新工具可用），且拥有对目标空间的读写权限。

> 🔧 **工具命名说明（重要）**：本章节用**逻辑工具名**（如 `search_by_mql`、`create_workitem`、`update_node`）指代能力，
> 实际调用名以当前客户端注册的前缀为准——例如 Codex 下为 `mcp__feishuprojectmcp__search_by_mql`（**全小写**），
> 其他客户端可能是 `mcp__FeishuProjectMcp__search_by_mql`。**不要照抄前缀大小写**，先确认当前环境实际暴露的工具名再调用。

### 同步步骤

#### 1. 读取配置与工单内容

读取 `config.json` 获取 `feishu_project` 配置,同时读取已生成的本地工单文件,提取四个维度内容:
- **问题标题** → 飞书项目工单 `name`
- **问题描述** → `field_d42436`（起因说明）
- **排查过程** → `field_d264eb`（排查过程）
- **问题总结** → `field_80a262`（问题总结）

> 📌 上述 `field_xxx` 为**示例键**,应以 `config.json` 的 `feishu_project.field_mapping` 为准。
> 若创建/查询报 `attribute key or value error` 或字段对不上,先用 `list_workitem_field_config`
> （传 `field_query` 模糊搜字段名）核对真实 `field_key`,再据实调用；不要凭印象猜字段名。

#### 2. 查找客户

用 MQL 在飞书项目中搜索客户:

```
search_by_mql   # 实际调用名以环境为准，如 mcp__feishuprojectmcp__search_by_mql
  project_key: <feishu_project.project_key>
  mql: SELECT `name`, `work_item_id` FROM `<project_key>`.`客户` WHERE `name` LIKE '%<客户名称>%' LIMIT 5
```

从结果中匹配客户名称,获取 `customer_work_item_id`。若搜索无结果或名称不匹配,询问用户确认客户名称或手动提供客户 ID。

> ⚡ **搜客户用最短关键词**:MQL 客户搜索较慢(单次可达 10~100 秒),`LIKE '%关键词%'` 里用**群名里的最短唯一词**(如「视波」「天天玩家」「噗」)通常一次命中;传客户全称反而更慢、也更容易因用词差异查不到。同一客户在一次任务里搜到后**缓存 `work_item_id`**,后续同客户工单直接复用,不重复搜。

#### 3. 组装工单名称

按 `naming.format` 模板组装工单名称。若模板中包含 `{customer_short_name}`，则从飞书项目客户名称中提取简称：

- **提取规则**：取客户名称中**第一个中文括号内的文本**，如 `（呸喽）广州呸喽呸喽科技有限公司` → `呸喽`。
- **兜底**：若名称中无括号，则使用完整客户名称。

若模板中使用的是 `{customer_name}`，则直接使用飞书项目中的完整客户名称。

#### 4. 创建工单

```
create_workitem   # 实际调用名以环境为准，如 mcp__feishuprojectmcp__create_workitem
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

> ⚠️ `create_workitem` 的 `fields` 中**必须包含** `defaults.field_values.template`（模板 ID），否则创建会失败。

#### 5. 设置排期与估分

创建成功后,用 `update_node` 设置默认排期和估分。**必须传 `clear_schedule: true`**,否则排期日期不会生效：

```
update_node   # 实际调用名以环境为准，如 mcp__feishuprojectmcp__update_node
  project_key: <feishu_project.project_key>
  work_item_id: <创建返回的 id>
  node_id: <feishu_project.schedule_node_id>
  node_schedule:
    clear_schedule: true
    points: <defaults.points>
    estimate_start_date: <当天 00:00:00 毫秒时间戳>
    estimate_end_date: <当天 23:59:59 毫秒时间戳>
    owners: ["<当前用户 user_key>"]
```

> ⚠️ **owners 用 `user_key`，不是 `open_id`**。飞书项目里排期负责人用 `user_key` 标识，
> 与 `config.json` 中 `target.open_id`（飞书 IM 的 open_id）不是同一套 ID。
> 取当前登录用户的 user_key：调用 `search_user_info` 传入 `current_login_user()`；
> 若要指定 target 本人，用其姓名/邮箱调 `search_user_info` 换取 user_key。

时间戳计算方式（北京时间 CST, UTC+8）:
```python
from datetime import datetime, timezone, timedelta
cst = timezone(timedelta(hours=8))
today = datetime.now(cst).date()   # 取“工单创建当天”，勿写死日期
start = datetime(today.year, today.month, today.day, 0, 0, 0, tzinfo=cst)
end = datetime(today.year, today.month, today.day, 23, 59, 59, tzinfo=cst)
start_ms = int(start.timestamp() * 1000)   # 当天起始
end_ms = int(end.timestamp() * 1000)       # 当天结束
```

#### 6. 验证同步结果（默认跳过）

`create_workitem` 与 `update_node` 返回成功即代表已正确写入,**默认不做回读验证**(可省去一次 5~30 秒的慢调用)。仅在以下情况才用 `get_workitem_brief` 回读:创建/更新返回异常或不确定;长文本字段疑似被截断;用户明确要求核对。回读发现不一致时,**以本地文件为准**用 `update_field` 修正。

> 开关:`config.json` 的 `feishu_project.verify_after_sync`(默认视为 `false`)。设为 `true` 时每单都回读验证;缺省或 `false` 时按上面的"仅异常才回读"执行。

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
5. **进入工单生成(受 `review.enabled` 约束)**:
   - 若 `config.json` 的 `review.enabled = false`(或缺省):完成分析后**直接进入工单生成流程**,无需等待用户确认。
   - 若 `review.enabled = true`:生成前**先按 `review.rules` 输出一段"待确认细节"**(如推断性的版本号归属、配置项名称、API 名称等),等用户确认后再写入工单;确认范围仅限这些推断性细节,不改变下面的 target 参与性硬性约束。
   - 无论开关如何,若用户对跳过项有异议,重申 target 参与性硬性约束规则,**不可妥协**。
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

---

## 性能优化与已知边界

### 执行提速建议（每次工单都应遵守）

1. **创建成功即完成**：`create_workitem` 返回成功即表示工单主体已正确写入，不需要再用 MQL 回读验证，可节省一次 8-10 秒的调用。
2. **本地文件与飞书同步并行**：本地 Markdown 文件写入和飞书工单创建互不依赖，可并行执行，无需等文件写完才开始飞书操作。
3. **客户 ID 缓存**：MQL 搜索客户较慢（~12 秒），同一个客户（如"冰川"）搜过一次后缓存其 `work_item_id`，后续同客户工单直接复用。
4. **边拉消息边分析**：不需要等所有消息全部拉完才开始归纳，拉到 5-10 条时就可以开始梳理问答主线，后续消息逐步补充。
5. **已知工具不需要再搜索**：钉钉 `dws chat` 和飞书项目 MCP 工具列表是固定的，不需要每次都跑 `tool_search`。
6. **并行发起互不依赖的调用**：搜群/查客户/查字段配置这类彼此无依赖的操作，放在同一批一起发起，不要一问一答串行等待。
7. **消息一次拉全**：飞书群消息用 `+chat-messages-list --no-reactions` 一次拉到位并直接打平展示，**不要先富集拉一遍再补拉一遍**（这是本项目里最常见的重复调用）。
8. **定位"关联来源/研发群"先用 `+chat-search`**：当第二个来源是"某工单标题 / TQA 研发排查群"时，直接用群名关键词 `+chat-search` 命中，**不要先拿标题去 `get_workitem_brief` 查工单**（客户成功空间里通常查不到，白等一次 404）。

### 常见坑与预判（避免踩雷浪费时间）

1. **飞书项目类型判断**：创建工单后若调用 `edit_wbs_draft` 返回 `Not Ipd Project`，说明该项目不是 IPD 类型，直接跳过排期设置即可，不需要重试（浪费 ~7 秒）。
2. **钉钉会话列表截断**：`chat list-all-conversations` 在 limit=100 时会返回 `hasMore=false` 但实际可能被截断，重要会话需用其他方式（如直接搜人、用对方 openDingtalkId 直接拉单聊）确认。
3. **跨组织单聊 ID 不通用**：从群成员中获取的 `openDingtalkId` 可能与单聊时使用的 ID 不一致，直接用群成员 ID 开单聊可能报 `AUTH_PERMISSION_DENIED`。此时应改用 `message list-all` 按发送者筛选，或等用户提供单聊会话 ID。
4. **跨组织授权生效时间**：`data-auth cross-org` 授予后，权限可能不会即时生效，可能需要重新登录或等待 1-2 分钟后再重试拉取单聊消息。
5. **MQL 日期字段与格式**：工单"创建时间"字段是 `start_time`（不是 `created_at`/`create_time`），**日期值用 `'YYYY-MM-DD'` 字符串**（如 `start_time >= '2026-07-13'`），传毫秒/秒时间戳会报 `not supported datetime format`。字段名报 `attribute key or value error` 时先用 `list_workitem_field_config` 核对，不要连续瞎试。
6. **`create_workitem` 长文本 JSON 转义**：排查过程/问题总结等长字段一次性写入时，注意 `field_value` 字符串里的换行、引号需正确转义，转义出错会报 `EOF while parsing a string`。稳妥做法是长中文直接原样传（避免手工拼 `\uXXXX` 出错），一次失败就检查转义再重试，不要反复试同一份坏数据。
7. **飞书接口整体偏慢**：`search_by_mql`/`create_workitem`/`update_node`/`get_workitem_brief` 普遍 5~30 秒、客户搜索偶发上百秒，属服务端延迟。对策是"少调用+能并行则并行+跳过非必要回读"，而不是重试（重试只会更慢）。
