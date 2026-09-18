---
name: dyz-ae-jumpserver-connect
description: 通过 SSH 连接数数科技 JumpServer 堡垒机（客户/内部），自动化登录目标主机。支持账号密码（默认）与密钥两种认证。当用户需要连接客户服务器、登录堡垒机、访问客户主机，或提到 jumpserver-customer.thinkingdata.cn / jumpserver-inner-v4.thinkingdata.cn 时触发。
agent_created: true
---

# JumpServer 堡垒机连接

通过 expect 脚本全自动 SSH 登录 JumpServer 堡垒机并连接到目标主机。支持**客户/私有化**与**内部/SaaS**两套配置，每套均支持**账号密码（默认）**与**密钥（备选）**两种认证。

## 工作流

### 第一步：确定堡垒机类型、登录方式并读取配置

**堡垒机类型**：
- **内部/SaaS**：用户提到"内部"、"内网"、"inner"、`jumpserver-inner` → 用 `references/config.md` 中「内部/SaaS」段。
- **客户/私有化**（默认）：未特别说明时走客户堡垒机 → 用 `references/config.md` 中「客户/私有化」段。

**登录方式**：
- **账号密码**（默认）：`auth=password`，`secret=` 该段 `JUMP_PASSWORD`，用户 `shuxiaozhi`。
- **密钥**（备选；仅用户明确要求或密码不可用时）：`auth=key`，`secret=` 该段 `JUMP_SSH_KEY`，用户 `dengyazhou`。

**账号权限（重要）**：涉及查询/排查操作时，**默认优先使用 `readonly` 账号**登录目标机（只读更安全）；
仅当用户明确要求写入/改配置时才用 `root`。
- 遇到 `ID>` 账号选择提示时，脚本**自动选 readonly**（解析账号列表取其 ID），无需人工干预；
- 需要强制用 root 时，显式把账号 ID 作为第 7 个参数传入（如 `"2"`）。

### 第二步：确定目标主机

- **用户已指定主机名/集群名**（如 "登录冰川-新"、"登录 pina"）→ 直接跳到第三步，把搜索词原样传给 JumpServer。
- **用户未指定** → **用纯文本提问**，让用户自由输入：

```
请告诉我要登录的目标主机名或集群名称（部分 IP / 主机名 / 备注均可）：
```

> ⚠️ 不要用 `ask` 工具配空选项——本宿主的 `ask` 强制要求 2-4 个选项，需要自由输入时直接用纯文本提问。

### 第三步：连接

```bash
expect <skill_dir>/scripts/connect.exp \
  <auth:key|password> <secret> <JUMP_USER> <JUMP_HOST> <JUMP_PORT> \
  "<搜索词>" [精确主机名]
```

示例（默认密码登录，内部堡垒机）：
```bash
expect <skill_dir>/scripts/connect.exp password '<JUMP_PASSWORD>' shuxiaozhi \
  jumpserver-inner-v4.thinkingdata.cn 2222 "技术交付测试机"
```

> `<skill_dir>` 动态解析：SKILL.md 文件所在的目录即为 skill 根目录，无需硬编码绝对路径。

## 搜索词注意事项（实战经验）

- **勿带节点分组前缀**：JumpServer 按「部分 IP / 主机名 / 备注」搜索；形如 `连接 - 运维-技术交付测试机-腾讯云-刘路` 中的 `连接 - ` 属于**节点分组路径**，带上会返回「没有资产」。去掉前缀、用资产名本身即可命中。
- **命中多台需给精确主机名**：出现 `[Host]>` 选择提示时须传第 7 个参数 `exact_host`；未传时脚本以退出码 2 退出并提示（不再空等超时）。
- **单资产多账号需选 ID**：出现 `ID>` 提示时（同一资产下有多个登录账号），**脚本自动优先选 `readonly`**（不传第 7 参数即可）；需强制 root 时把账号 ID 作为第 7 个参数传入（如 `"2"`）。脚本最多连续处理 3 轮选择提示（可应对"先选主机、再选账号"的链式提示）。
- **搜索无结果**以退出码 3 退出，提示检查搜索词。
- **提示可能逐字符换行**（如 `技\n术\n交\n付…`、乃至 `O\np\nt\n>`），属正常现象；脚本已用 `\s*` 放宽匹配 `Opt>`、`[Host]>`、`ID>`，不影响输入。
- **同一搜索词在不同登录账号下命中结果可能不同**（资产/账号可见范围不同）：例如豹亮对 `shuxiaozhi` 仅 `readonly` 一个账号（唯一命中、直连），对 `dengyazhou` 则有 `readonly` + `root` 两个账号（触发 `ID>` 提示）。

### 账号选择（ID>）示例

```bash
# 默认：自动选 readonly（推荐，无需第 7 参数）
expect <skill_dir>/scripts/connect.exp key ~/.ssh/dyz_customer.jumpserver.pem dengyazhou \
  jumpserver-customer.thinkingdata.cn 2222 "豹亮"

# 需强制 root 时：显式传账号 ID（豹亮 readonly=1 / root=2）
expect <skill_dir>/scripts/connect.exp key ~/.ssh/dyz_customer.jumpserver.pem dengyazhou \
  jumpserver-customer.thinkingdata.cn 2222 "豹亮" "2"
```

## 如何确认登录身份（shuxiaozhi / dengyazhou）

脚本启动即回显一行身份信息（最省事）：

```
>>> 堡垒机 jumpserver-inner-v4.thinkingdata.cn:2222  |  账号 shuxiaozhi  |  认证方式 password
```

另有两处佐证：
- `spawn ssh …` 行中的 `用户名@主机`（如 `shuxiaozhi@…` / `dengyazhou@…`）；
- 登录后欢迎横幅的**显示名**：`shuxiaozhi` → **数小智**，`dengyazhou` → **邓亚洲**。

对应关系：`auth=password` ⇒ `shuxiaozhi`（数小智）；`auth=key` ⇒ `dengyazhou`（邓亚洲）。

## 脚本：scripts/connect.exp

```
用法: connect.exp <auth:key|password> <secret> <jump_user> <jump_host> <jump_port> <search_term> [exact_host]
```

自动化流程：
1. 按 `auth` 生成 SSH 命令：
   - `key` → `ssh -i <secret> <user>@<host> -p<port>`
   - `password` → `ssh -o PubkeyAuthentication=no -o PreferredAuthentications=password -o NumberOfPasswordPrompts=1 …`，等 `password:` 提示后自动送密码
2. 等 `Opt>` 菜单（`\s*` 放宽，兼容逐字符换行）→ 发送搜索词
3. 处理交互提示（最多 3 轮循环，可应对链式提示）：唯一命中 → 直接进入目标机；`[Host]>`（多台主机）→ 按第 7 参数选择（未给则退出码 2）；`ID>`（单资产多账号）→ **自动优先选 readonly**，需指定时按第 7 参数选择；「没有资产」→ 退出码 3
4. 检测终端类型：交互式终端 → `interact` 保持会话；非 TTY（Bash 工具） → 发 `exit` 后**立即退出**（不等 `eof`：堡垒机 logout 后回到 `[Host]>` 而不关闭连接，等 `eof` 会空耗整个 timeout）

**退出码**：`0` 成功 · `1` 参数错误/超时/认证失败 · `2` 命中多台主机需指定主机名，或多账号资产未找到 readonly · `3` 搜索无结果

## 自测（修改本 skill 后必须执行）

**维护规范：每次改动 `SKILL.md` / `scripts/connect.exp` / `references/config.md` 后，必须跑一次自测并确保全绿**，防止改动破坏既有登录路径（尤其是逐字符换行、多账号选择这类易回归的交互细节）。

```bash
./scripts/selftest.sh              # 全部用例（离线 + 内部 + 客户），约 12 秒
./scripts/selftest.sh --offline    # 只跑离线参数校验，秒级、不联网
./scripts/selftest.sh --quick      # 离线 + 内部堡垒机（跳过客户）
```

**用例清单（8 个）**：

| # | 用例 | 断言 |
|---|---|---|
| 1 | 无参数 | 打印 Usage，退出码 1 |
| 2 | 非法 `auth` 值 | 报错，退出码 1 |
| 3 | 参数不足（缺搜索词） | 打印 Usage，退出码 1 |
| 4 | 内部堡垒机 + 密码（shuxiaozhi） | 退出码 0，含 `Connected to target host successfully` |
| 5 | 内部堡垒机 + 密钥（dengyazhou） | 退出码 0，`认证方式 key` |
| 6 | 客户堡垒机 + 密码（shuxiaozhi） | 退出码 0 |
| 7 | 客户堡垒机 + 密钥（dengyazhou，不传第 7 参） | 退出码 0，输出含 `readonly`（验证 ID> 自动选 readonly） |
| 8 | 客户堡垒机 + 显式账号 `ID=2` | 退出码 0，进入 `[root@` |

**要点**：
- 凭据（密码/密钥路径）由 `selftest.sh` 从 `references/config.md` **解析获得**，脚本内不硬编码；测试输出中 secret 一律显示为 `<secret>`，不泄露密码。
- 测试会**真实登录堡垒机**并产生审计日志，属只读行为（登录 → 确认身份 → 立即退出），不执行任何写操作。
- 默认目标是测试机（内部 `运维-技术交付测试机-腾讯云-刘路`、客户 `豹亮`）；可用环境变量覆盖：
  `INNER_SEARCH=… CUSTOMER_SEARCH=… ./scripts/selftest.sh`
- 断言依据是 `connect.exp` 的**退出码（0/1/2/3）+ 关键输出行**；失败时打印实际输出末 25 行便于定位。
- 全部通过退出码 0，任一失败退出码 1（可用于 CI / pre-commit）。
- 若本次改动引入了新的交互分支（新的提示符类型等），应在 `selftest.sh` 中补对应用例。

## 依赖

- 需要安装 `expect`（macOS 预装）
- 账号密码登录：无额外依赖
- 密钥登录：私钥文件必须可访问
- 自测：仅用 `bash` + `awk` + `grep`（已兼容 macOS 自带 bash 3.2）
