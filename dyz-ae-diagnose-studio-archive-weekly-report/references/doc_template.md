# 飞书文档结构与填充规则（占比优先样式，2026-09 定稿版）

> 用 lark-doc XML 生成。整篇刷新用 `docs +update --command overwrite`（本统计文档无图片/评论，安全）。
> 先把快照数据填成 `<name>.xml` 放 cwd（相对路径），再 `--content @<name>.xml`。
> 标题唯一：`<title>diagnose-studio 本周归档统计 YYYY-MM-DD</title>`。

## 章节骨架（编号按实际插入的「占比」章节顺延）

1. **callout 概览**：`<callout emoji="📊" background-color="light-blue" border-color="blue">`
   - 一句话：本周归档 X 个（历史累计 Y）：计入统计 A（网页端 W + MCP 通道 M）+ 批量导入 S（末节单列）+ 已排除 liuchunwei E 条。
   - 状态百分比：已解决 r%（值 r）· 未定位 u%（值 u）· 未标记 n%（值 n）；未定位中已优化 k 条。
2. **一、统计口径**：目标机/DB/时间窗/快照时间/口径说明（统计含网页端与 MCP 通道；排除批量导入与 liuchunwei，并注明「已排除 liuchunwei 的 N 条」；口径内容照抄 config.md）。
   - **⚠️ 硬规则：正文面向业务/支持同学，禁止出现任何数据库字段名与表名**（`outcome`、`fix_status`、`source`、`created_at`、`owner`、`archives`/`tasks`/`users`、`scan-import` 等一律换成业务说法）。改后措辞（2026-09-24 定稿，直接照抄这三句）：
     - 数据源句：「数据源：内部堡垒机 jumpserver-inner-v4 → 主机「运维-技术交付测试机-腾讯云-刘路」（ta1）上的 diagnose-studio 归档库 **/root/diagnose-studio/studio/studio.db**。」（不列表名）
     - 时间窗句：「时间窗：<起> ~ <止>（服务端当前时刻，含当日最新归档与结论/优化补标——即会话新增、后来补写的结论和优化标记都已算进来）。」（不写 `outcome`）
     - 口径句：「口径：**统计包含网页端与 MCP 通道（[mcp]数小智）发起的用户会话**，两者都是真实使用；**排除批量导入的历史归档**（那是把归档目录里的旧记录一次性扫进库，入库时间会被记成创建时间，内容多为更早时间的旧问题，不代表本周排查工作量，见第八节单列）；**已排除 liuchunwei 的 N 条**（该账号的会话都是 MCP 通道测试/占位内容）。」
   - 自检句用中文来源名（「网页端 35 + MCP 通道 1 + 来源未标注 2」），不要写 `web`/`mcp`/`owner`。
3. **二、会话状态占比（核心关注）**：
   - mermaid 饼图（新增即由 create/overwrite 创建 whiteboard block）：
     ```xml
     <whiteboard type="mermaid">pie
         title 会话状态占比（共A个）
         &quot;已解决 R&quot; : R
         &quot;未定位 U&quot; : U
         &quot;未标记 N&quot; : N</whiteboard>
     ```
     （mermaid 内双引号必须写成 `&quot;`，换行保留）
     **⚠️ 关键坑 1：`pie` 与 `title` 必须分行写**——写成一行 `pie title 会话状态占比（共A个）` 会被 lark 判为 `degrade_code=2107 Whiteboard content parse failed` 并丢弃整块画板（2026-09-24 实测：一行式 create 与 block_insert_after 补插均失败，分行后立即成功）。
     **⚠️ 关键坑 2：饼图不得出现值为 0 的扇区**（如 `&quot;未定位 0&quot; : 0`）——同样报 `degrade_code=2107` 并把整块降级丢弃（文档只剩表格、画板缺失）。故只列非零状态，0 值信息（如未定位 0）由下方占比表承载。
     **⚠️ 关键坑 3：`docs +update --command overwrite` 丢画板是高概率偶发，必须当常态防**——2026-09-24 同日 3 次 overwrite 实测：2 次报 `degrade_code=2107`（`result=partial_success`）且文档里画板消失；1 次同一套 XML 正常保留、`warnings` 为空。即**同一份内容时而成功时而失败，无法靠改写法规避**。故 **overwrite 之后一律 `docs +fetch` 检查 `<whiteboard` 是否存在（应为 1），别只看 `ok=true` / `warnings`**（周内原地刷新是常态路径，缺失就按下条补插；2026-09-24 已实测补插可用）。
     若 create/overwrite 已发生降级，可单独补插：先 `docs +fetch --detail with-ids` 取「二、」标题的 block_id，再 `docs +update --command block_insert_after --block-id <id> --content -`（stdin 传 mermaid；stdin 里双引号直接写 `"` 即可，已验证成功）。
   - 占比表：状态 | 会话数 | 占比（R/A、U/A、N/A，保留 1 位小数）。
   - 附注：结论标记率 (R+U)/A；可给「含批量导入+被排除 owner 口径」对照（把 scan-import S 与被排除 owner E 一并计入时总量与未标记率如何变化）。
4. **三、按人统计**：列 = 用户 | 会话数 | 已解决 | 未定位 | 未标记 | **结论标记率**。不含被排除 owner（liuchunwei）与批量导入。
   - 表下可注明来源构成（如「网页端 W 条 + MCP 通道 M 条」）；批量导入与被排除 owner 均不在表内。
5. **四、按 skill 分布**：列 = skill | 会话数 | 已解决 | 未定位 | 未标记 | **已解决率** | **是否优化**。
   - 「是否优化」单元格：`未定位 X · 已优化 Y`；X/Y 口径见 config.md，**Y 不是 resolved 数**。
   - **表下口径说明必须用业务语言，禁止出现数据库字段名**（如 `fix_status`、`optimized`、`resolved`）——读者是业务/支持同学，不认字段名。给读者的措辞照抄这段：
     「口径说明：**已解决率** = 该 skill 已解决数 ÷ 该 skill 会话数。**是否优化**列描述的是未定位会话的后续优化跟进，「未定位 X · 已优化 Y」中：X = 该 skill 未定位的条数，Y = 其中**已经在排查工作台里标记「已优化」**的条数。Y 反映的是未定位问题里的优化进度，**不是已解决数**。」
     （内部实现口径仍是 unresolved 中 `fix_status='optimized'` 条数，写作措辞与内部口径不要混。）
6. **五、按客户/集群分布**：正文逗号句 + 注（空 cluster 条数、ID: 归正说明、其他疑似脏值）。
7. **六、本周未标记清单**：表 时间 | 用户 | skill | 客户/集群 | 问题摘要（question 截 50-70 字、换行转空格）；可加「来源」列标注 web/mcp。
8. **七、备注**：结论口径 + 未定位已优化/待优化明细（引用快照）。口径句同样**不得出现 `fix_status`/`optimized` 等字段名**，用：
   「结论口径：**已解决**、**未定位**、**未标记**（没写结论）三者互斥，每条会话只属于其中一种；**是否优化**是对**未定位**会话额外打的「已优化」标记（在排查工作台里手工标），与上边三种结论是两回事，不混在一起算。」
9. **八、批量导入历史归档（单列，不计入统计）**：内部取数口径 = 来源 `archives.source='scan-import'`（归档目录扫描入库，`created_at`=导入时刻、内容为更早时间的旧问题）；按「skill × 状态」汇总 + 导入时间范围 + 条数。**但正文同样不写字段名**，改用：「来源为**批量导入的历史归档**（把归档目录里的旧记录一次性扫描入库；入库时间会被记成创建时间，内容多是更早时间的旧问题）。**本次窗口内 N 条**，故不影响上方任何统计口径。」并保留说明「属历史归档批量入库，不代表本周实际排查工作量」。

## XML 细节（避免返工的踩坑清单）
- 数字列对齐用 `<colgroup><col width="80"/>…`；表头 `<th background-color="light-gray">`；
- 合计行加粗 `<b>`；行内 `<br/>` 表示换行；`&` 写 `&amp;`；
- 状态列配色可选：已解决列数字用绿色 `<span text-color="green">`、未定位橙色、未标记灰（保持朴素亦可）；
- 表格单元格文本若含引号/特殊字符注意 XML 转义；mermaid 内容除 `&quot;` 外勿转义标签。

## 完成后（默认新建周文档，按周隔离）
- **默认：`docs +create --parent-token ITPUwjPeIiW4oWkYGzocsi9CnVe --content @<xml> --as user`** —— 每周执行都新建一篇独立文档并挂在 wiki 目录《每周diagnose-studio归档统计》下（`<title>` 内日期=统计周周一），不覆盖历史周的文档；创建成功后把 URL 交给用户并登记。
  - 已误建在云空间时用 `wiki +move --obj-type docx --obj-token <doc> --target-space-id 7620832102451285220 --target-parent-token ITPUwjPeIiW4oWkYGzocsi9CnVe` 迁入。
- 仅当用户显式给 token 要求原地更新（如同周刷新）才用 `docs +update --doc <token> --command overwrite --content @<xml> --as user`。
- 校验：`docs +fetch --doc <token>` 核对合计行/占比/是否优化 Y/未标记行数/`<whiteboard token>` 存在；
- 清理 cwd 下临时 xml。
