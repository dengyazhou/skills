# 飞书文档结构与填充规则（占比优先样式，2026-09 定稿版）

> 用 lark-doc XML 生成。整篇刷新用 `docs +update --command overwrite`（本统计文档无图片/评论，安全）。
> 先把快照数据填成 `<name>.xml` 放 cwd（相对路径），再 `--content @<name>.xml`。
> 标题唯一：`<title>diagnose-studio 本周归档统计 YYYY-MM-DD</title>`。

## 章节骨架（编号按实际插入的「占比」章节顺延）

1. **callout 概览**：`<callout emoji="📊" background-color="light-blue" border-color="blue">`
   - 一句话：本周归档 X 个（历史累计 Y）：计入统计 A（网页端 W + MCP 通道 M）+ 批量导入 S（末节单列）。
   - 状态百分比：已解决 r%（值 r）· 未定位 u%（值 u）· 未标记 n%（值 n）；未定位中已优化 k 条。
2. **一、统计口径**：目标机/DB/时间窗/快照时间/口径说明（统计含 web 与 mcp，仅排除 scan-import；照抄 config.md 相关句）。
3. **二、会话状态占比（核心关注）**：
   - mermaid 饼图（新增即由 create/overwrite 创建 whiteboard block）：
     ```xml
     <whiteboard type="mermaid">pie title 会话状态占比（共A个）
         &quot;已解决 R&quot; : R
         &quot;未标记 N&quot; : N</whiteboard>
     ```
     （mermaid 内双引号必须写成 `&quot;`，换行保留）
     **⚠️ 关键坑：饼图不得出现值为 0 的扇区**（如 `&quot;未定位 0&quot; : 0`）——lark 会报 `degrade_code=2107 Whiteboard content parse failed` 并把整块降级丢弃（文档只剩表格、画板缺失）。故只列非零状态，0 值信息（如未定位 0）由下方占比表承载。
     若 create/overwrite 已发生降级，可单独补插：先 `docs +fetch --detail with-ids` 取「二、」标题的 block_id，再 `docs +update --command block_insert_after --block-id <id> --content -`（stdin 传 mermaid）。
   - 占比表：状态 | 会话数 | 占比（R/A、U/A、N/A，保留 1 位小数）。
   - 附注：结论标记率 (R+U)/A；可给「含批量导入口径」对照（把 scan-import S 一并计入时总量与未标记率如何变化）。
4. **三、按人统计**：列 = 用户 | 会话数 | 已解决 | 未定位 | 未标记 | **结论标记率**。含 MCP 会话的 owner（如 liuchunwei/zhangshengwen）。
   - 表下可注明来源构成（如「MCP 通道 M 条、网页端 W 条」），批量导入不在表内（末节单列）。
5. **四、按 skill 分布**：列 = skill | 会话数 | 已解决 | 未定位 | 未标记 | **已解决率** | **是否优化**。
   - 「是否优化」单元格：`未定位 X · 已优化 Y`；X/Y 口径见 config.md，**Y 不是 resolved 数**。
   - 表下注明两个口径（是否优化 / 已解决率）。
6. **五、按客户/集群分布**：正文逗号句 + 注（空 cluster 条数、ID: 归正说明、其他疑似脏值）。
7. **六、本周未标记清单**：表 时间 | 用户 | skill | 客户/集群 | 问题摘要（question 截 50-70 字、换行转空格）；可加「来源」列标注 web/mcp。
8. **七、备注**：outcome 口径 + 未定位已优化/待优化明细（引用快照）。
9. **八、批量导入历史归档（单列，不计入统计）**：来源 `archives.source='scan-import'`（归档目录扫描入库，`created_at`=导入时刻、内容为更早时间的旧问题）；按「skill × 状态」汇总 + 导入时间范围 + 条数。正文说明"属历史归档批量入库，不代表本周实际排查工作量"。

## XML 细节（避免返工的踩坑清单）
- 数字列对齐用 `<colgroup><col width="80"/>…`；表头 `<th background-color="light-gray">`；
- 合计行加粗 `<b>`；行内 `<br/>` 表示换行；`&` 写 `&amp;`；
- 状态列配色可选：已解决列数字用绿色 `<span text-color="green">`、未定位橙色、未标记灰（保持朴素亦可）；
- 表格单元格文本若含引号/特殊字符注意 XML 转义；mermaid 内容除 `&quot;` 外勿转义标签。

## 完成后（默认新建周文档，按周隔离）
- **默认：`docs +create --parent-token EGqlwLYG9ihxnGkVd6UcuEphnob --content @<xml> --as user`** —— 每周执行都新建一篇独立文档并挂在 wiki 目录《每周diagnose-studio归档统计》下（`<title>` 内日期=统计周周一），不覆盖历史周的文档；创建成功后把 URL 交给用户并登记。
  - 已误建在云空间时用 `wiki +move --obj-type docx --obj-token <doc> --target-space-id 7314274064414457859 --target-parent-token EGqlwLYG9ihxnGkVd6UcuEphnob` 迁入。
- 仅当用户显式给 token 要求原地更新（如同周刷新）才用 `docs +update --doc <token> --command overwrite --content @<xml> --as user`。
- 校验：`docs +fetch --doc <token>` 核对合计行/占比/是否优化 Y/未标记行数/`<whiteboard token>` 存在；
- 清理 cwd 下临时 xml。
