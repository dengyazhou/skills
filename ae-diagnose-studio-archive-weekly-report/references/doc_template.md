# 飞书文档结构与填充规则（占比优先样式，2026-09 定稿版）

> 用 lark-doc XML 生成。整篇刷新用 `docs +update --command overwrite`（本统计文档无图片/评论，安全）。
> 先把快照数据填成 `<name>.xml` 放 cwd（相对路径），再 `--content @<name>.xml`。
> 标题唯一：`<title>diagnose-studio 本周归档统计 YYYY-MM-DD</title>`。

## 章节骨架（编号按实际插入的「占比」章节顺延）

1. **callout 概览**：`<callout emoji="📊" background-color="light-blue" border-color="blue">`
   - 一句话：本周归档 X 个（历史累计 Y）：人工 A + 自动化 M（单列第八节）。
   - 人工状态百分比：已解决 r%（值 r）· 未定位 u%（值 u）· 未标记 n%（值 n）；未定位中已优化 k 条。
2. **一、统计口径**：目标机/DB/时间窗/快照时间/排除自动化说明（照抄 config.md 相关句）。
3. **二、人工会话状态占比（核心关注）**：
   - mermaid 饼图（新增即由 overwrite 创建 whiteboard block）：
     ```xml
     <whiteboard type="mermaid">pie title 人工会话状态占比（共A个）
         &quot;已解决 R&quot; : R
         &quot;未定位 U&quot; : U
         &quot;未标记 N&quot; : N</whiteboard>
     ```
     （mermaid 内双引号必须写成 `&quot;`，换行保留）
   - 占比表：状态 | 会话数 | 占比（R/A、U/A、N/A，保留 1 位小数）。
   - 附注：结论标记率 (R+U)/A；并给「含自动化口径」对照（自动化 M 全未标记时：未标记 (N+M)/(A+M) 被拉高多少）。
4. **三、按人统计**：列 = 用户 | 会话数 | 已解决 | 未定位 | 未标记 | **结论标记率**。
   - 自动化账号（如 liuchunwei）不在表内，表下注明"均为自动化通道会话，见第八节"。
5. **四、按 skill 分布**：列 = skill | 会话数 | 已解决 | 未定位 | 未标记 | **已解决率** | **是否优化**。
   - 「是否优化」单元格：`未定位 X · 已优化 Y`；X/Y 口径见 config.md，**Y 不是 resolved 数**。
   - 表下注明两个口径（是否优化 / 已解决率）。
6. **五、按客户/集群分布**：正文逗号句 + 注（空 cluster 条数、ID: 归正说明）。
7. **六、本周未标记清单**：表 时间 | 用户 | skill | 客户/集群 | 问题摘要（question 截 50-70 字、换行转空格）。
8. **七、备注**：outcome 口径 + 未定位已优化/待优化 3 条明细（引用快照）。
9. **八、自动化通道会话（单列）**：来源 [mcp]数小智 · liuchunwei 账号 · skill 均为 code-diagnose · 全部未标记；明细表 时间 | skill | 问题摘要。正文说明"若计入将掩盖真实人工指标"。

## XML 细节（避免返工的踩坑清单）
- 数字列对齐用 `<colgroup><col width="80"/>…`；表头 `<th background-color="light-gray">`；
- 合计行加粗 `<b>`；行内 `<br/>` 表示换行；`&` 写 `&amp;`；
- 状态列配色可选：已解决列数字用绿色 `<span text-color="green">`、未定位橙色、未标记灰（保持朴素亦可）；
- 表格单元格文本若含引号/特殊字符注意 XML 转义；mermaid 内容除 `&quot;` 外勿转义标签。

## 完成后
- 若为覆盖更新：`docs +update --doc <token> --command overwrite --content @<xml> --as user`
- 若新建：`docs +create --content @<xml> --as user`（标题写在 `<title>` 内）
- 校验：`docs +fetch --doc <token>` 核对合计行/占比/是否优化 Y/未标记行数/`<whiteboard token>` 存在；
- 清理 cwd 下临时 xml。
