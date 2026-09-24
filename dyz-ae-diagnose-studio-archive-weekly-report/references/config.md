# dyz-ae-diagnose-studio-archive-weekly-report 连接与目标配置

## 默认目标（可被调用参数覆盖）

| 项 | 值 | 说明 |
|---|---|---|
| 堡垒机 | `jumpserver-inner-v4.thinkingdata.cn` 端口 `2222`，用户 `dengyazhou` | 内部堡垒机（JumpServer v4 菜单 `Opt>`） |
| SSH key | `~/.ssh/dyz_inner.jumpserver.pem` | 内部堡垒机专用，勿用客户堡垒机 key |
| 目标主机搜索词 | `运维-技术交付测试机-腾讯云-刘路` | JumpServer 资产/备注；唯一匹配直接登录（root@10.206.16.4，主机名 ta1） |
| 归档库 DB | `/root/diagnose-studio/studio/studio.db` | ta1 上 diagnose-studio 部署的 SQLite 元数据库（archives/tasks/users） |
| 统计起点 | **自动：本周一 00:00 → 服务器当前时刻**（周一起始日随执行日自动计算） | 每次执行固定拉取本周最新数据（含当日），无需传参；确需自定义窗口时才传 `--since YYYY-MM-DD` |
| 飞书目标 | **每次执行为当前统计周新建独立文档**（标题《diagnose-studio 本周归档统计 YYYY-MM-DD》，YYYY-MM-DD=统计周周一） | 按周隔离，绝不覆盖历史周文档；仅用户显式给 token 时才原地覆盖 |
| **飞书目录（wiki 父节点）** | 节点《每周diagnose-studio归档统计》：node_token `EGqlwLYG9ihxnGkVd6UcuEphnob`，space_id `7314274064414457859` | **所有周文档必须建在这个 wiki 节点下**：`docs +create --parent-token EGqlwLYG9ihxnGkVd6UcuEphnob ...`；若先建在云空间再迁入，用 `wiki +move --obj-type docx --obj-token <doc> --target-space-id 7314274064414457859 --target-parent-token EGqlwLYG9ihxnGkVd6UcuEphnob` |
| 历史周文档 | 均在同一 wiki 归档目录下：**2026-09-04 周** docx `DUiRdEqmWo1PhTx9F1BcRbBxnMc`（wiki node `IjbIwOvn6i1B0Ek57L5cFa7cnCe`） | **2026-09-07 周** docx `GIHAdzwSYoFFjkxaomtctteknbc`（wiki node `DSJmwuakGi46V0ktaHycE9uBnXd`）；**2026-09-14 周** docx `Re1pdJdoUoUL8OxxrLxc2XsQnGh`（wiki node `R4i6wKOv9iMWi7kgHatcbfvQnMc`）（每周执行后在此追加一行） |
| 远程执行 | `python3`（ta1 自带；无 sqlite3 CLI 依赖） | 脚本用 base64 管道规避 shell 引号 |

## 口径开关（默认全开）

- **统计口径 = 排除 `scan-import` + 排除指定 owner（默认 `liuchunwei`）**（用排除法而非仅取 `source='web'`，以兼容早期 source 为空的历史记录）。三类来源处理：
  - `web`（网页端发起）：**计入统计**；
  - `mcp`（[mcp]数小智 通道发起，`tasks.source='mcp'`）：**也属用户真实使用，计入统计**（用户明确要求）；脚本第 8/8c 节给出 MCP 与 web 的来源明细，便于对照；
  - `scan-import`（归档目录扫描入库的历史归档）：**单列第九节，不计入统计**。created_at 为导入时刻而非原始排查时刻，会一次性灌入大量更早的历史问题（如 2026-09-14 17:15:19 一次性导入 81 条，内容为 2026-07~08 问题），混入会严重扭曲本周占比与人均工作量；
- **排除 owner（默认 `liuchunwei`）**：该账号本周会话均为 MCP 通道测试/占位内容（`【原始问题】`/`__SKIP__`/`完全无关的问题 xyz` 等），不代表真实排查工作量，**从统计口径中排除**（用户 2026-09-18 明确要求，长期生效）。脚本第 10 节单列被排除的会话，便于核对；文档中只需在「统计口径」注明一句「已排除 liuchunwei 的 N 条」，不必列明细。可用 `--exclude-owner a,b` 改多个，传空串 `--exclude-owner ""` 禁用排除；
- `archives.cluster` 脏值 `ID:` → 归正 `Garena`（google_ads Push 回传失败归档）；另见「其他脏值」：`优化`/`使用`/`TE`/`App` 等为问题文本误提取，暂如实呈现；
- 「是否优化」列：`未定位 X`=unresolved 数；`已优化 Y`=unresolved 中 `fix_status='optimized'` 条数（非 resolved 数）。

## 数据一致性注意

- WAL 模式（studio.db-wal），查询用一次连接内跑完全部统计，避免跨时刻不一致；
- 会话与 outcome/修复标记随时可能被补标 → 每次产出带快照时间（远端 `date`/python time）；
- 同一快照内用交叉合计自检：**统计口径 + scan-import + 被排除 owner = 本周全量**，且 统计口径 = web + mcp（脚本第 1 节「本周来源分布」、第 8/8c 节、第 9/10 节可核对）。
