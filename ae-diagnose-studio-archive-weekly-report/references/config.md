# ae-diagnose-studio-archive-weekly-report 连接与目标配置

## 默认目标（可被调用参数覆盖）

| 项 | 值 | 说明 |
|---|---|---|
| 堡垒机 | `jumpserver-inner-v4.thinkingdata.cn` 端口 `2222`，用户 `dengyazhou` | 内部堡垒机（JumpServer v4 菜单 `Opt>`） |
| SSH key | `~/.ssh/dyz_inner.jumpserver.pem` | 内部堡垒机专用，勿用客户堡垒机 key |
| 目标主机搜索词 | `运维-技术交付测试机-腾讯云-刘路` | JumpServer 资产/备注；唯一匹配直接登录（root@10.206.16.4，主机名 ta1） |
| 归档库 DB | `/root/diagnose-studio/studio/studio.db` | ta1 上 diagnose-studio 部署的 SQLite 元数据库（archives/tasks/users） |
| 统计起点 | **自动：本周一 00:00 → 服务器当前时刻**（周一起始日随执行日自动计算） | 每次执行固定拉取本周最新数据（含当日），无需传参；确需自定义窗口时才传 `--since YYYY-MM-DD` |
| 飞书目标 | 既有文档 `DUiRdEqmWo1PhTx9F1BcRbBxnMc`（《diagnose-studio 本周归档统计》） | 默认覆盖刷新；或 `+create` 新建 |
| 远程执行 | `python3`（ta1 自带；无 sqlite3 CLI 依赖） | 脚本用 base64 管道规避 shell 引号 |

## 口径开关（默认全开）

- 排除自动化通道：`tasks.source='mcp'`（[mcp]数小智 → liuchunwei 账号、code-diagnose、全部未标记）单列第八节，不计入人工统计；
- `archives.cluster` 脏值 `ID:` → 归正 `Garena`（google_ads Push 回传失败归档）；
- 「是否优化」列：`未定位 X`=unresolved 数；`已优化 Y`=unresolved 中 `fix_status='optimized'` 条数（非 resolved 数）。

## 数据一致性注意

- WAL 模式（studio.db-wal），查询用一次连接内跑完全部统计，避免跨时刻不一致；
- 会话与 outcome/修复标记随时可能被补标 → 每次产出带快照时间（远端 `date`/python time）；
- 同一快照内用交叉合计自检：按人合计 = skill 合计 = 全量 − mcp。
