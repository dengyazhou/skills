# ae-diagnose-studio-archive-weekly-report 连接与目标配置

## 默认目标（可被调用参数覆盖）

| 项 | 值 | 说明 |
|---|---|---|
| 堡垒机 | `jumpserver-inner-v4.thinkingdata.cn` 端口 `2222`，用户 `dengyazhou` | 内部堡垒机（JumpServer v4 菜单 `Opt>`） |
| SSH key | `~/.ssh/dyz_inner.jumpserver.pem` | 内部堡垒机专用，勿用客户堡垒机 key |
| 目标主机搜索词 | `运维-技术交付测试机-腾讯云-刘路` | JumpServer 资产/备注；唯一匹配直接登录（root@10.206.16.4，主机名 ta1） |
| 归档库 DB | `/root/diagnose-studio/studio/studio.db` | ta1 上 diagnose-studio 部署的 SQLite 元数据库（archives/tasks/users） |
| 统计起点 | **自动：本周一 00:00 → 服务器当前时刻**（周一起始日随执行日自动计算） | 每次执行固定拉取本周最新数据（含当日），无需传参；确需自定义窗口时才传 `--since YYYY-MM-DD` |
| 飞书目标 | **每次执行为当前统计周新建独立文档**（标题《diagnose-studio 本周归档统计 YYYY-MM-DD》，YYYY-MM-DD=统计周周一） | 按周隔离，绝不覆盖历史周文档；仅用户显式给 token 时才原地覆盖 |
| 历史周文档 | 2026-09-04 周：`DUiRdEqmWo1PhTx9F1BcRbBxnMc` | 2026-09-07 周：`GIHAdzwSYoFFjkxaomtctteknbc`；**2026-09-14 周：`Re1pdJdoUoUL8OxxrLxc2XsQnGh`**（每周执行后在此追加一行） |
| 远程执行 | `python3`（ta1 自带；无 sqlite3 CLI 依赖） | 脚本用 base64 管道规避 shell 引号 |

## 口径开关（默认全开）

- **统计口径 = 排除 `scan-import`**（用排除法而非仅取 `source='web'`，以兼容早期 source 为空的历史记录）。三类来源处理：
  - `web`（网页端发起）：**计入统计**；
  - `mcp`（[mcp]数小智 通道发起，`tasks.source='mcp'`）：**也属用户真实使用，计入统计**（用户明确要求）；脚本第 8/8c 节给出 MCP 与 web 的来源明细，便于对照。注意 MCP 会话的 owner 不固定（liuchunwei/dengyazhou/zhangshengwen 等都有），并非只有机器账号；
  - `scan-import`（归档目录扫描入库的历史归档）：**单列第九节，不计入统计**。created_at 为导入时刻而非原始排查时刻，会一次性灌入大量更早的历史问题（如 2026-09-14 17:15:19 一次性导入 81 条，内容为 2026-07~08 问题），混入会严重扭曲本周占比与人均工作量；
- `archives.cluster` 脏值 `ID:` → 归正 `Garena`（google_ads Push 回传失败归档）；另见「其他脏值」：`优化`/`使用`/`TE`/`App` 等为问题文本误提取，暂如实呈现；
- 「是否优化」列：`未定位 X`=unresolved 数；`已优化 Y`=unresolved 中 `fix_status='optimized'` 条数（非 resolved 数）。

## 数据一致性注意

- WAL 模式（studio.db-wal），查询用一次连接内跑完全部统计，避免跨时刻不一致；
- 会话与 outcome/修复标记随时可能被补标 → 每次产出带快照时间（远端 `date`/python time）；
- 同一快照内用交叉合计自检：**统计口径 + scan-import = 本周全量**，且 统计口径 = web + mcp（脚本第 1 节「本周来源分布」与第 8/8c 节可核对）。
