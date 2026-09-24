---
name: dyz-ae-ticketRecord
description: >
  将钉钉/飞书/本地文件中的客户支持对话,聚焦"对指定对象的提问 + 该对象的回答",
  归纳为结构化的工单记录,按【问题标题】【问题描述】【排查过程】【问题总结】四个维度输出。
  支持同步到飞书项目(客户成功空间),自动创建工单并设置排期估分。
  总结对象和飞书项目配置由本 skill 目录下的 config.json 配置。
  触发词:工单记录、ticketRecord、对接群总结、支持对话归纳、dyz-ae-ticketRecord、ae-ticketRecord、同步飞书项目。
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

> ⚡ **自主执行原则（默认行为，无需反复确认）**
> 本 skill **一次执行到底**，中途不向用户提确认性问题。具体地：
> - **输入源**：能从用户消息或上下文判断就直接用，不要反问"你指的是哪个群/哪个文件"。
> - **分类判断**（工单类型_内容 / 工单类型_TS / 估分 / 排期）：按本文件的规则**自主判定**，不询问。
> - **推断性内容**：拿不准时按最合理的写法**自主完成**，在交付时用一句话标注（如"推断：xxx"）供事后核对，**不要中断流程**。
> - **同步飞书项目**：`config.json` 中 `feishu_project.enabled = true` 即视为已授权，**直接执行创建与排期**，不询问是否同步。
> - **例外**：仅当遇到**无法自行解决**的硬阻塞（如客户在飞书项目中确实搜不到、`config.json` 缺失或不可读）才向用户提问，且一次问清。
> - 若 `config.json` 中 `review.enabled = true`，才需要"生成前展示待确认细节供审核"；当前为 `false`。

## 第一步(必做):读取配置

每次执行**必须先**用 `Read` 工具读取本 skill 目录下的 `config.json`:

- `target.name`:总结对象的姓名(用于匹配聊天记录中的发言人署名,钉钉/飞书通用)
- `target.open_id`:总结对象的飞书 open_id(仅飞书场景使用,用于匹配 `<mention-user id="...">` 提及;钉钉场景下忽略此字段)
- `target.aliases`:别名列表(辅助匹配,跨平台通用)
- `output.dir`:工单记录的**存档目录**
- `output.filename_template`:文件名模板,支持占位符 `{title}`(项目/群名)与 `{date}`(YYYYMMDD)
- `output.weekly_dir_convention`:周目录规则(若存在)。规则含义:在 `output.dir` 下插入一层周目录,目录名为**执行归档当天所属周的周一日期**(YYYY-MM-DD)。⚠️ 以**记录当天**算,**不是**以对话发生日期算;文件名中的 `{date}` 才取对话发生日期
- `feishu_project.ticket_type`:「工单类型_内容」字段配置(见「工单类型_内容 自动分类」)
- `feishu_project.ticket_type_ts`:「工单类型_TS」字段配置(见「工单类型_TS 自动分类」)

后续归纳**只围绕这个 target 展开**。若 `config.json` 缺失或无法读取,先提示用户配置后再继续。

### open_id 校验

读取配置后,在实际消息中匹配 target 时,留意消息里 target 实际出现的 `sender.id`（飞书 open_id）或 `senderOpenDingTalkId`（钉钉）。若与 `config.json` 中记录的 `target.open_id` 不一致：

1. **不要静默忽略**——open_id 不一致可能意味着 config 配置已过期,或匹配到了同名其他人。
2. 以姓名/aliases 匹配到的消息中实际出现的 ID 为准,**直接用 `Edit` 工具更新 `config.json` 中的 `target.open_id`**,并在交付时告知用户："已将 config 中 open_id 由 `xxx` 更新为 `yyy`"。**不要为此中断流程询问**。

此校验可避免因 open_id 过期导致 target 消息漏匹配。

## 输入源

输入可以是以下任意一种,**优先从用户消息或上下文自主识别**;仅当完全无法判断时才向用户确认:

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
3. 拿不准是否相关时,**自主判断**（同一任务/同一故障的不同现场→合并;互不相关的独立问题→各自出单）,并在交付时说明合并/拆分依据,不打断流程询问。
4. **合并工单的命名**:`{title}` 取能概括整件事的名称(如"天梯夜幕之下项目LogBus容量评估"),而非其中某个单一群名。

## 读取方式

- **钉钉私聊/群聊**:使用 `dws chat` 系列命令直接拉取 JSON 格式消息(无需手动解析文档)。命令返回的每条消息已包含 `sender`(发言人姓名)、`senderOpenDingTalkId`、`content`(文本内容,图片/文件为占位说明)、`createTime`(时间)。拉取后直接按 JSON 字段匹配 target,无需正则或 HTML 解析。
  - **钉钉群消息拉取顺序**：`dws chat search --query "<群名>"` 取 `openConversationId` → `dws chat message list --group <openConversationId> --time "YYYY-MM-DD 00:00:00" --direction newer --limit 200`（`--direction newer` 从该时间往现在拉；返回为**倒序**，需自行按 `createTime` 正序整理）。
  - **钉钉图片/文件可下载**（截图常含关键证据，建议在有价值时下载读取）：
    ```bash
    dws chat message download-media --type mediaId \
      --resource-id '<mediaId，取 content 中 mediaId= 后的值，含开头的 $>' \
      --message-id '<消息的 openMessageId>' \
      --open-conversation-id '<openConversationId>' \
      --output ./img.png
    ```
    ⚠️ 参数名**不是** `--media-id`；`--type mediaId`、`--resource-id`、`--message-id`、`--open-conversation-id` 四者均必填，缺一报 `unknown flag`/参数校验错。
- 飞书文档:用 `lark-cli docs +fetch --doc "<URL 或 token>" --as user --format json` 读正文;若只给了标题,先 `lark-cli docs +search --query "<标题>" --as user --format json` 取到文档 URL/token,再 `+fetch`。
- 本地纯文本文件(`.md`、`.txt`等):用 `Read` 工具读取。
- 聊天记录中的图片通常是辅助截图,可不展开;如内容关键,按上述方式下载后读取分析。钉钉消息中的图片显示为 `[图片消息](mediaId=@xxx)`,文件显示为 `[文件] xxx`,附件名可读。

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
10. **URL 一律用 `[标题](url)` 显式 markdown 格式**:禁止写裸 URL,尤其禁止把裸 URL 放进中文括号或让其紧跟全角标点(如 `（https://xxx），请客户参照...`)。原因:URL 后紧跟无空白的全角字符时,markdown 自动链接会一路吃到行尾,把后续中文正文吞进链接目标导致链接损坏——飞书项目与本地 `.md` 均会踩此坑(GFM 会裁剪尾部半角标点,但全角 `）` 不在其裁剪集内)。链接标题优先取目标文档的真实标题。

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

当 `config.json` 中 `feishu_project.enabled = true` 时,**默认执行以下流程**（无需用户要求、也无需再确认）；仅当用户明确表示跳过同步时才不执行。**同步前必须先完成本地文件的生成,以本地文件内容为准。**

### 前置条件

需 **`meegle` CLI 已安装并处于登录态**（飞书项目官方 CLI，npm 包 `@lark-project/meegle`），且拥有对目标空间的读写权限。

```bash
meegle auth status   # authenticated 必须为 true；false 时先登录再同步
```

- **未安装**：`npx -y @lark-project/meegle@latest install --host project.feishu.cn --device-code --lang zh`
- **未登录/已过期**：`meegle auth login --device-code`（输出授权 URL 后在浏览器完成授权）
- access token 约 2 小时过期。

> 🔧 **token 过期时的自主恢复（实测有效，无需打断用户）**
> CLI 自身**不会**用 keychain 里的 refresh_token 自动续期，过期后直接报 `no local token`。可直连 OAuth 端点续期：
> ```bash
> # 从 keychain 取 refresh_token 与 client_id（macOS）
> security find-generic-password -s meegle-cli -a default -w   # JSON: access_token/refresh_token/expires_at/client_id
>
> # 换取新 token（必须 form-urlencoded，JSON 方式会报 invalid_client）
> curl -sS -k -X POST 'https://project.feishu.cn/mcp_server/oauth/token' \
>   -H 'Content-Type: application/x-www-form-urlencoded' \
>   --data-urlencode "grant_type=refresh_token" \
>   --data-urlencode "refresh_token=<refresh_token>" \
>   --data-urlencode "client_id=<client_id>"
> # → {"access_token":"o-...","expires_in":7200,"refresh_token":"<不变>"}
> ```
> 拿到新 token 后用环境变量注入本次调用，**不改 keychain**：
> ```bash
> MEEGLE_USER_ACCESS_TOKEN="o-..." meegle workitem create ...
> MEEGLE_USER_ACCESS_TOKEN="o-..." meegle auth status    # 应返回 authenticated: true
> ```
> ⚠️ **refresh_token 不会轮换**（多次刷新返回同值），故刷新**不会破坏用户登录态**。
> ⚠️ 沙盒内**无法写回 keychain**（`Operation not permitted`），所以用户终端仍显示旧 token；如需其终端恢复，请用户在自己终端执行一次 `meegle auth status`。

### 工单类型_内容 自动分类

**字段**:`feishu_project.ticket_type.field_key`(当前为 `field_f91b3e`,select)。
同步时**必须根据问题性质从三个选项中选择**,**不得固定写死为"问题排查"**。选项及判定规则:

| 类型 | option_id | 特征 | 典型场景 |
|---|---|---|---|
| **日常咨询** | `ckj86uudm` | 纯知识/流程性问答,不涉及故障、数据异常或修复诉求;target 以"回答/解释/给指引"即可闭环,无需排查定位 | SDK 如何获取/下载、索取文档/链接、某功能是否支持、如何配置/接入、版本咨询 |
| **问题排查** | `v64s_gkxw` | 客户报告实际异常/故障/数据问题,需定位原因;最终由客户侧处理或仅解释原因,数数侧**无开发/修复/升级动作** | 数据拉取失败、上报不到/查不到数据、数据延迟/差异/丢失/重复、任务失败、报错、压测异常、组件不可用 |
| **内部需求/问题修复** | `w6mxbmakg` | 数数侧**主动执行**开发/修复/升级/内部变更并有落地动作(数数内部发新版修复、数数执行 LogBus/组件升级、产品功能修复、数据修复/回溯、内部需求跟进) | SDK 新版本由数数侧发布修复、LogBus/组件升级由数数执行、产品功能修复、数据修复/回溯、内部需求跟进 |

**判断优先级**(同一工单可能混合多类,按下述顺序判定,命中即止):

1. **数数侧主动执行开发/修复/升级/内部变更落地** → `内部需求/问题修复`(判定锚点:【问题总结】中出现"数数已发布新版 SDK / 数数侧已修复 / 数数执行升级 / 内部跟进 / 研发处理"等**数数主动落地**动作)
2. **否则,按「对话形态」二分** —— 这是 `日常咨询` 与 `问题排查` 的**唯一主判据**:

   | 形态 | 特征 | 归类 |
   |---|---|---|
   | **解释型** | 客户问"为什么 / 该怎么写 / 是否支持";数数侧**告知规则、用法、文档、正确配置**即可闭环;**无需进入环境、无需逐项排查** | `日常咨询` |
   | **排查型** | 客户报"出故障了 / 数据不对";数数侧**进入环境实际排查**——登录服务器或后台、查日志/抓包、逐项比对、逐账户验证、多轮定位,最终**定位到具体故障点** | `问题排查` |

   - **判定锚点(关键)**:看【排查过程】里数数侧**实际做了什么**,而**不是**看"根因最终归属谁"。
     - 仅**告知/指引**(给文档、给写法、给规则、解释机制)→ **解释型 → `日常咨询`**
     - **实际执行排查动作**(登录环境、看日志、命令行验证、逐项/逐账户核对、定位到具体对象)→ **排查型 → `问题排查`**
   - ⛔ **不要用"根因归属客户侧"去否定问题排查**:根因落在客户侧配置/传参的工单,**既可能是日常咨询、也可能是问题排查**,取决于数数侧是"解释清楚"还是"排查定位"。这是最容易误判之处。
   - 🔸 **补充情形——已确认缺陷/故障类**:若数数侧结论是"**确实存在问题**"(SDK/产品缺陷、环境异常、配置失效等,**不论责任归属**),**即使未做环境排查、只是直接告知修复版本**,仍归 **`问题排查`**。
     - 典型:客户报崩溃,数数侧直接答"这是已知问题,升级到 X 版本即可修复"——虽属"告知动作",但确认了**缺陷存在**,归 `问题排查`(若数数侧还发布了修复版本,则升级为 `内部需求/问题修复`)。
     - 与"客户用法问题"的区别:此类**没有"你应该这样用"的纠正**,而是**承认产品侧存在问题**。
3. **否则**(无实质问答、仅信息同步类)→ 按语义最贴近的类别选择。

> 📌 **回测锚点(判不准时对照这五例,均已被用户确认)**:
>
> | 工单 | 数数侧实际动作 | 正确归类 |
> |---|---|---|
> | 智品·神策转换数据查不到(客户漏传用户标识) | 核对字段后**告知入库规则** | 日常咨询 |
> | 淦源·鸿蒙 eventData 未解析(客户传参未平铺) | 看日志后**告知正确写法** | 日常咨询 |
> | 心流·三方方案并存致成本翻倍(客户配了两套方案) | **告知**用 `#thirdparty_entity_id` 区分 | 日常咨询 |
> | 远略·鸿蒙埋点查不到(实为报表缓存) | **抓日志、查初始化 API、核对入库、比对分组** | 问题排查 |
> | 岸边·Meta 拉取失败(方案含失效账户) | **ssh 登录、逐账户 curl 验证、逐项定位失效 ID** | 问题排查 |
>
> 共同规律:**「告知」→ 日常咨询;「排查定位」→ 问题排查**(与根因归属哪一侧无关)。

**边界细化——"问题排查" vs "内部需求/问题修复"**:
- 根因是**数数旧版 SDK/产品缺陷**,但修复动作**由客户侧升级应用执行、数数侧仅给出方案与文档指导、无内部开发/发布动作** → 归 **`问题排查`**(典型:指导客户升级 SDK 修复旧版缺陷)
- 数数侧**有内部落地动作**(发布新版本、执行升级、修复代码、数据修复/回溯等)→ 归 **`内部需求/问题修复`**
- 判断时看【问题总结】里修复动作的**执行方**:数数主动执行 → 内部需求/问题修复;客户执行、数数仅指导 → 问题排查

**边界细化——"日常咨询" vs "问题排查"(易错,务必按此判定)**:
- ❌ **不要按"根因归属谁"判**（旧规则,已废弃）：根因落在客户侧配置/传参 → 一律归日常咨询，这个逻辑**是错的**，它把"经过实质排查才定位到"的工单错误降级了。
- ✅ **按"数数侧做了告知还是排查"判**：
  - 数数侧**只需告知**（给文档/写法/规则/机制解释）→ **`日常咨询`**
  - 数数侧**必须进入环境排查才能定位**（登录、看日志、命令行验证、逐项核对）→ **`问题排查`**，**即使最终根因是客户侧的配置/传参问题**
- 反例记忆：**远略**（根因是报表缓存）与**智品**（根因是客户漏传字段）都表现为"数据查不到"，但前者经过抓日志+核对入库+比对分组 → 问题排查；后者只需核对字段+告知规则 → 日常咨询。**区别在数数侧付出了哪种动作，不在根因归属。**

判断时以工单【问题描述】【排查过程】【问题总结】三部分整体为依据,忠实原文,不臆测。若拿不准,自主选定最贴合的类型,并在交付时用一句话标注(如"推断：工单类型_内容选 X")供事后核对,**不中断流程**。

### 工单类型_TS 自动分类

**字段**:`feishu_project.ticket_type_ts.field_key`(当前为 `field_c69400`,tree-select,**单选一个叶子节点**)。
同步时**根据问题所属的技术域/环节选择最贴合的叶子节点**,**不得固定写死为"数据集成/客户端SDK"**。完整选项树(含 option_id)见 `config.json` 的 `ticket_type_ts.options`。常用映射:

| 问题归属(技术域) | TS 类型(路径) | 典型场景 |
|---|---|---|
| 客户端 SDK | 数据集成 > 客户端SDK | Android/iOS/Web/Unity/Cocos/鸿蒙/快游戏等客户端 SDK 接入、上报、配置、日志、SDK 缺陷 |
| 服务端 SDK | 数据集成 > 服务端SDK | Go/Python/Java 等服务端 SDK 上报问题 |
| Restful API | 数据集成 > Restful API | 服务端 Restful API 上报(返回 -1、字段缺失、鉴权等) |
| LogBus | 数据集成 > Logbus | 日志传输卡住、LogBus 安装/升级/配置(含升级 LogBus2) |
| 三方平台数据 | 数据集成 > 三方数据集成 | 巨量/广点通/Unity Ads/AdMob/AppsFlyer 等第三方广告、归因平台的数据拉取与接入 |
| 其他数据接入工具 | 数据集成 > 对应子项 | DataX、BatchImporter、DataTransfer、Logstash、二开工具、TE数据规则等 |
| 数据差异/质量 | 数据差异 > 对应子项 | 数据丢失、数据延迟、数据重复、错误入库、用户绑定、数据量排查 |
| 分析平台功能 | 分析产品 > 对应子项 | 看板报表、分析模型、标签分群、数据表、埋点管理、指标预警、项目/系统管理、OpenAPI |
| 运营任务 | 运营产品 > 对应子项 | 推送/运营任务异常、通道异常、运营数据异常 |
| 组件/集群 | 组件异常 > 对应组件 或 集群卡顿 | Presto/Trino/Kafka/Hive/Kudu 等组件异常、集群卡顿、任务调度失败(调度方案) |
| 数据操作单项 | 对应叶子 | 历史数据导入、实时数据接入、数据导出、数据删除、数据去重、数据修复、外表映射、三方脚本迁移 |
| 方案类 | 技术方案 > 对应子项 或 方案设计 | 数据集成方案、数据修复方案、数据导出方案、非标准方案、跨源/多集群/跨项目方案 |
| AE Agent | AE Agent > AE Agent | AE Agent 相关问题 |
| 功能测试验证 | 功能测试验证 | 版本验证、功能验收测试 |

**判断优先级**:

1. 先定位问题**发生的环节**(客户端SDK / 服务端SDK / Restful API / LogBus / 三方集成 / 数据差异 / 分析产品 / 运营产品 / 组件异常 / 数据操作单项 / 技术方案 等),选择对应的叶子节点。
2. 无法明确归入上述技术域时,选择语义最贴近的叶子,并在交付时标注;不中断流程。
3. 两个类型字段**独立判断、同时设置**:
   - 「工单类型_内容」= 处理**性质**(日常咨询 / 问题排查 / 内部需求/问题修复)
   - 「工单类型_TS」= 问题所属**技术环节**(如 SDK 缺陷需更新版本 → 内容=内部需求/问题修复、TS=数据集成>客户端SDK)

### 同步步骤

#### 1. 读取配置与工单内容

读取 `config.json` 获取 `feishu_project` 配置,同时读取已生成的本地工单文件,提取四个维度内容:
- **问题标题** → 飞书项目工单 `name`
- **问题描述** → `field_d42436`（起因说明）
- **排查过程** → `field_d264eb`（排查过程）
- **问题总结** → `field_80a262`（问题总结）

#### 2. 查找客户

用 MQL 在飞书项目中搜索客户:

```bash
MQL="SELECT \`name\`, \`work_item_id\` FROM \`客户\` WHERE \`name\` LIKE '%<客户名称>%' LIMIT 5"
meegle workitem query --project-key <feishu_project.project_key> --mql "$MQL"
```

从返回的 `data."1"[*].moql_field_list` 里按 `key` 取值（`string_value` / `long_value`），匹配客户名称后获取 `customer_work_item_id`。

> ⚠️ **MQL 字段名必须用项目真实字段名**——写错时 CLI 会直接给出候选（如 `创建人` → 建议 `创建者`、`工作项ID` → 建议 `work_item_id`），照提示改正后重试即可,不要臆造字段名。
> ⚠️ **shell 转义**：MQL 用反引号包裹字段名、单引号包裹字符串,在 bash 双引号内需转义反引号（`` \` ``）,如上例;整条 MQL 也可改用 `--params` 传 JSON 规避转义。

若搜索无结果或名称不匹配,**先自主放宽匹配**（试简称、去掉括号/地域后缀、换关键字再查一次）；确实搜不到时才向用户确认客户名称或请其提供客户 ID。

#### 3. 组装工单名称

按 `naming.format` 模板组装工单名称。若模板中包含 `{customer_short_name}`，则从飞书项目客户名称中提取简称：

- **提取规则**：取客户名称中**第一个中文括号内的文本**，如 `（呸喽）广州呸喽呸喽科技有限公司` → `呸喽`。
- **兜底**：若名称中无括号，则使用完整客户名称。

若模板中使用的是 `{customer_name}`，则直接使用飞书项目中的完整客户名称。

#### 4. 判断工单类型字段

- **工单类型_内容**(`ticket_type.field_key`):按「工单类型_内容 自动分类」规则三选一。
- **工单类型_TS**(`ticket_type_ts.field_key`):按「工单类型_TS 自动分类」规则选择叶子 option_id(对应父级路径)。

两个字段各自独立判断,均不得使用固定默认值。

#### 5. 创建工单

```bash
meegle workitem create --project-key <feishu_project.project_key> --work-item-type <feishu_project.work_item_type> --format json \
  --fields '[{"field_key":"name","field_value":"<组装后的工单名称>"},{"field_key":"<field_mapping.customer_id>","field_value":"<客户 work_item_id>"},{"field_key":"<field_mapping.customer_name>","field_value":"<客户名称文本>"},{"field_key":"<field_mapping.问题描述>","field_value":"<【问题描述】内容>"},{"field_key":"<field_mapping.排查过程>","field_value":"<【排查过程】内容>"},{"field_key":"<field_mapping.问题总结>","field_value":"<【问题总结】内容>"},{"field_key":"<ticket_type.field_key>","field_value":"<步骤 4 判断的工单类型_内容 option_id>"},{"field_key":"<ticket_type_ts.field_key>","field_value":"<步骤 4 判断的工单类型_TS 叶子 option_id>"},{"field_key":"template","field_value":"214223"}]'
```

`--fields` 传**一个 JSON 数组**，按 `config.json` 的 `field_mapping` 与 `defaults.field_values` 组装；`defaults.field_values` 的每个键值都要并入同一数组。创建成功后从返回中取 `work_item_id`，供后续 `workitem update` / `workflow update-node` 使用。

> 🚨 **`field_value` STRING 协议（硬约束，实测）**：协议层 `field_value` 固定为字符串,**传数字会被服务端直接拒绝**（`argument ...field_value must be string, got number`）。
> - 标量（number / bool / option_id / work_item_id / 毫秒时间戳）**一律加引号写成字符串**，如 `"214223"`、`"v64s_gkxw"`、`"7769675"`；
> - 数组、对象**必须先 JSON.stringify** 再传（如 multi-user → `"[\"<userkey>\"]"`，直接传数组报 `need STRING type, but got: LIST`）；
> - ⚠️ `config.json` 的 `defaults.field_values` 中 `template` 等键是**数字**，合并时必须转成字符串 `"214223"`。
>
> ⚠️ 三个正文字段是 `multi-text`，直接传 markdown 字符串即可；内容含换行 / 引号 / 反引号时按 JSON 规则转义。命令长、正文含特殊字符时，**建议用 python 拼好 `fields` 数组再 `subprocess.run(cmd)`**，避免 shell 转义踩坑。
> ⚠️ 需批量创建多条工单时**必须串行执行**（逐条调用），禁止并发，否则会触发平台限流。

> ⚠️ **已知兼容性处理（重要）**：当「工单类型_内容」判断为 `内部需求/问题修复`（`w6mxbmakg`）时，**直接与 `field_c69400`（工单类型_TS）一起创建会被飞书侧拒绝**（报"级联选项字段值层级无效"——该内容类型下 TS 字段的创建校验不通过）。
> **处理方式**：先以「问题排查」（`v64s_gkxw`）+ 判断出的 TS 叶子创建工单，创建成功后再改 `field_f91b3e`：
>
> ```bash
> meegle workitem update --project-key <feishu_project.project_key> --work-item-id <创建返回的 work_item_id> \
>   --fields '[{"field_key":"field_f91b3e","field_value":"w6mxbmakg"}]'
> ```
>
> 其余两个内容类型（`ckj86uudm` 日常咨询 / `v64s_gkxw` 问题排查）可直接与 TS 一起创建，无需特殊处理。

#### 6. 设置排期与估分

创建成功后,用 `update_node` 设置默认排期和估分。**必须传 `clear_schedule: true`**,否则排期日期不会生效：

```bash
meegle workflow update-node --project-key <feishu_project.project_key> \
  --work-item-id <创建返回的 work_item_id> \
  --node-id <feishu_project.schedule_node_id> \
  --node-schedule '{"clear_schedule":true,"points":0.1,"estimate_start_date":1789920000000,"estimate_end_date":1789920000000,"owners":["<当前用户 user_key>"]}'
```

- **`owners` 填 user key**（形如 `7106308666671775745`），**不是 open_id**——用 `meegle user me` 取当前登录用户的 `user_key`（或 `meegle user search --user-keys current_login_user()`）。
- ⚠️ `--node-schedule` 是**原生 JSON 参数**，与 `--fields` 的 STRING 协议**相反**：`points` 必须是**数字**（传 `"0.1"` 会报 `must be number, got string`），时间戳是数字，`owners` 是字符串数组。

### 自动估分

**字段**：`defaults` 不再固定 `points`，估分按聊天内容自动评估（依据 `feishu_project.estimate_points`），**不得写死为 0.1**。规则：

1. **基础分**由「工单类型_内容」决定：
   - 日常咨询 `ckj86uudm` → **0.1**
   - 问题排查 `v64s_gkxw` → **0.1**
   - 内部需求/问题修复 `w6mxbmakg` → **0.2**

2. **加分项**（每命中一项 +0.1；以【问题描述】【排查过程】【问题总结】为判定依据）：
   - **多轮深度排查**：仅对**排查型**工单适用——【排查过程】中有 **≥4 个实质排查步骤**，且包含**进入环境/逐项核对**类动作（登录服务器或后台、查日志/抓包、命令行验证、逐账户或逐项比对），最终经多轮往返才定位到具体故障点。
     - ⚠️ **不算**的情形：仅"告知用法/给文档/解释规则"的**解释型**工单；仅对话条数多、但排查动作浅的工单。
   - **数数侧开发落地**：数数侧更新 SDK / 修复代码 / 执行升级 / 内部变更（含发布新版本修复）。

3. ⛔ **不作为加分项**（这些**不等于**工作量大）：
   - 跨天处理（对话跨越 2 天及以上）
   - 多群协作（工单由多个群/文档合并）
   - 单纯的消息条数多、对话轮次多

4. **取值约束**：0.1 步进，最小 0.1，最大 1.0；四舍五入到 0.1 的整数倍。

5. **判定锚点**：以本地工单文件的四维度内容为依据，忠实原文，不臆测；拿不准时按最贴近的档位自主定值，并在交付时标注。

> 📌 **回测锚点（估分判不准时对照，均已被用户确认）**：
>
> | 工单 | 类型 | 命中加分 | 估分 |
> |---|---|---|---|
> | 智品·神策转换数据查不到 | 日常咨询 | 无 | 0.1 |
> | 淦源·鸿蒙 eventData 未解析 | 日常咨询 | 无 | 0.1 |
> | 心流·三方方案并存致成本翻倍 | 日常咨询 | 无 | 0.1 |
> | 远略·鸿蒙埋点查不到 | 问题排查 | 多轮深度排查 | **0.2** |
> | 岸边·Meta 拉取失败 | 问题排查 | 多轮深度排查 | **0.2** |
> | 池骋·iOS 退出崩溃 | 问题排查 | 数数侧开发落地（发 3.5.2） | **0.2** |
> | 掌声·PHP SDK track 失败 | 内部需求/问题修复 | 基础分 0.2 | **0.2** |
>
> 规律：**日常咨询一律 0.1；问题排查/内部需求 视是否命中加分项落在 0.1~0.3。**

**排期日期取对话发生日期范围**（依据 `feishu_project.schedule_date`）：
- 排期起始 = **对话开始日期** 00:00:00（与文件名 `{date}` 一致）
- 排期结束 = **对话结束日期** 23:59:59
- **单日对话**：开始=结束=对话发生日期
- **跨天对话**：排期覆盖 开始日 00:00:00 ~ 结束日 23:59:59 的完整时间范围
- **不取执行当天**
- 若无法确定对话日期，退回执行当天并在交付时标注

时间戳计算方式（北京时间 CST, UTC+8），以跨天对话为例：
```python
from datetime import datetime, timezone, timedelta
cst = timezone(timedelta(hours=8))
start = datetime(2026, 8, 17, 0, 0, 0, tzinfo=cst)   # 对话开始日期
end = datetime(2026, 8, 18, 23, 59, 59, tzinfo=cst)  # 对话结束日期
start_ms = int(start.timestamp() * 1000)   # 开始日期起始
end_ms = int(end.timestamp() * 1000)       # 结束日期结束
```

#### 7. 验证同步结果

```bash
meegle workitem get --project-key <feishu_project.project_key> --work-item-id <id> --fields _all
meegle workflow get-node --project-key <feishu_project.project_key> --work-item-id <id> --node-id-list <feishu_project.schedule_node_id>
```

回读确认工单名称、工单类型（`field_f91b3e` / `field_c69400`）、四维正文、排期与估分是否已正确写入；
`get-node` 返回的 `schedule` 里 `estimate_start_time` / `estimate_finish_time` / `points` 即实际排期与估分。
若字段内容与本地文件不一致,**以本地文件为准**用 `meegle workitem update`（字段）/ `meegle workflow update-node`（排期）修正。

> ⚠️ **已知坑：「总工时」(`field_23458b`) 可能未随排期汇总**（偶发，实测多次）
> 设置排期后 `points` 已正确，但工单的「总工时」字段仍为 0 或空。**回读时务必一并核对总工时**；若未同步，**重跑一次同样的 `update-node` 命令**即可触发汇总（通常数秒后生效）。

### 关键规则

1. **以本地文件为准**——所有字段内容以本地工单文件为准,不在同步时额外增删内容。
2. **客户名称以飞书项目为准**——群聊名称可能与飞书项目客户名称不一致,创建工单时取飞书项目中查到的正式客户名称。
3. **`clear_schedule: true` 必传**——不传此参数排期日期不会写入节点。
4. **总排期按对话发生日期范围**——`estimate_start_date` 取对话开始日期 00:00:00、`estimate_end_date` 取对话结束日期 23:59:59（跨天覆盖完整时间范围；单日开始=结束），不取执行当天。
5. **同步失败不阻塞本地**——若 `meegle` 未安装 / 未登录或创建失败,本地工单文件照常生成,提示用户手动同步。
6. **工单类型动态判断**——`ticket_type.field_key`(工单类型_内容)必须按「工单类型_内容 自动分类」规则三选一,**禁止固定为"问题排查"**。
7. **工单类型_TS 动态判断**——`ticket_type_ts.field_key`(工单类型_TS)必须按「工单类型_TS 自动分类」规则选择叶子节点,**禁止固定为"数据集成/客户端SDK"**。
8. **「内部需求/问题修复」创建兼容处理**——当「工单类型_内容」为 `w6mxbmakg` 时,先以 `v64s_gkxw` 创建工单,创建成功后再用 `meegle workitem update` 将 `field_f91b3e` 改为 `w6mxbmakg`(飞书侧创建校验拒绝 w6mxbmakg+TS 组合)。

## 执行步骤

1. **读取 `config.json`,确定总结对象 target 和飞书项目配置。**
2. 识别/确认输入源(钉钉私聊/群聊、飞书文档标题或 URL、本地文件路径),**先完整通读全部消息**(按时间顺序逐条读完,理清对话脉络与因果关系),再进入分析环节。不可边读边下结论,避免凭前几条消息的印象对根因做出与原文不符的判断。
3. 按上面的判定规则,筛出"对 target 的提问"与"target 的回答"主线,识别所有问题点。
4. **预过滤（target 参与性检查）**：对识别出的每个问题，检查 target 是否有**实质性回答**（即至少有一条由 target 发出的消息，或 target 在排查链中有实质贡献）。
   - **有回答** → 标记为"待生成工单"。
   - **无回答**（target 被 @ 但未作答、或问题由其他同事全程处理）→ **标记为"跳过"**，不生成工单。
   - ⛔ **此规则为硬性约束**：即使用户明确要求"所有问题都出工单"、"这个问题也记录一下"、或声称"N 个问题就要 N 个工单"，只要 target 未参与回答，**必须拒绝生成**并解释原因。可建议用户："该问题由 XX 全程处理，如需记录建议切换总结对象或手动创建工单。"
   - 若所有问题均被跳过，告知用户"本期消息中未发现 target 参与回答的问题"，不生成任何工单文件，流程结束。
5. **直接进入工单生成**：完成分析后直接进入工单生成流程并完成存档与同步，**全程不等待用户确认**。若用户对跳过项有异议，重申硬性约束规则，**不可妥协**。
6. 多问题合并:提炼一个统一【问题标题】。
7. 按四维度成文,遵守归纳规则(尤其:不出现 target 姓名、根因要点明)。
8. 输出归纳结果;**默认直接落地存档**（用户说"记录工单"即视为要存档,不必再问）。**先重新 `Read` 一次 `config.json` 取最新的 `output.dir`、`output.filename_template` 和 `output.weekly_dir_convention`(不要复用本轮早些时候缓存的值,配置可能已被改动)**,再按以下规则生成完整路径:

   **路径生成规则**:
   1. 若 `output.weekly_dir_convention` 存在(非空),则在 `output.dir` 下插入一层周目录。周目录名称为**执行归档当天所属周的周一日期**(格式 YYYY-MM-DD)。⚠️ **以记录当天算,不是以对话/工单日期算**。例如:今天是 20260804(周二),则周目录为 `2026-08-03`,无论所归纳的对话发生在哪一天。
   2. 最终路径 = `output.dir` / `周目录(如有)` / `filename_template 渲染结果`。文件名中的 `{date}` 取**对话发生日期**(与周目录的取值口径不同,不要混用)。
   3. 举例:`output.dir=/xxx/output`, `weekly_dir_convention` 有值,今天 20260804(该周周一 20260803),对话发生于 20260731, `filename_template=工单记录_{title}_{date}.md` → 最终路径 `/xxx/output/2026-08-03/工单记录_生境-项目配置链接_20260731.md`。
   4. 若 `weekly_dir_convention` 不存在或为空,则路径 = `output.dir` / `filename_template 渲染结果`(无周目录层)。
   5. ⚠️ `output.dir` 下可能存在早期遗留的**周日**命名目录(如 `2026-06-22`、`2026-06-29`),**不代表现行规则**,不要参照它们反推口径。
   6. 若目录不存在则先 `mkdir -p` 创建完整路径。
9. **默认直接同步**：除用户明确表示跳过、或 `feishu_project.enabled = false` 外,一律按「同步到飞书项目」章节执行（**不再询问是否同步**）,其中「工单类型_内容」「工单类型_TS」均按自动分类规则判断,不固定默认值。
10. **输出跳过报告**：若步骤 4 中有问题被跳过（target 未参与回答），在所有工单生成完毕后，追加一段摘要告知用户哪些内容未生成工单：

```
⏭ 已跳过（target 未参与回答）：
- 问题简述 A
- 问题简述 B
```

此报告让用户知晓哪些群内讨论未被记录，便于后续按需补录或转交其他同事处理。

## 技能维护规范(供更新本技能时遵守)

1. **更新前先读取当前 SKILL.md / config.json 全文**,理解现有结构与已有内容,再决定修改点。
2. **按理解做增量修改**,只新增缺失的能力/规则,不整段重复追加已有内容。
3. **幂等校验**:任何"应用/复制"操作后,检查目标文件——章节标题、配置键不得重复出现;若发现重复,先清理再确认。
4. 本文件与 config.json 由同一份改动同步维护,保持一致性。
