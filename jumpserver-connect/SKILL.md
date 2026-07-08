---
name: jumpserver-connect
description: 通过 SSH 连接数数科技客户 JumpServer 堡垒机，自动化登录目标主机。当用户需要连接客户服务器、登录堡垒机、访问客户主机，或提到 jumpserver-customer.thinkingdata.cn 时触发。
agent_created: true
---

# JumpServer 堡垒机连接

通过 expect 脚本全自动 SSH 登录 JumpServer 堡垒机并连接到目标主机。

## 工作流

### 第一步：读取配置

读取 `references/config.md` 获取 SSH 连接参数（密钥、用户、地址、端口）。

### 第二步：确定目标主机

- **用户已指定主机名/集群名**（如 "登录冰川-新"、"登录 pina"）→ 直接跳到第三步，把搜索词原样传给 JumpServer。堡垒机能搜到用户权限范围内的所有主机。
- **用户未指定**（如 "登录堡垒机"、"连接客户机器"）→ 用 `AskUserQuestion` 询问，**不预设任何选项**，让用户自由输入：

```
question: "请输入要登录的目标主机名或集群名称："
header: "目标主机"
options: []   ← 不提供任何预设选项，用户直接在输入框键入
```

### 第三步：连接

执行 skill 目录下的 expect 脚本。脚本路径为当前 SKILL.md 所在目录下的 `scripts/connect.exp`。

```bash
expect <skill_dir>/scripts/connect.exp \
  <JUMP_SSH_KEY> <JUMP_USER> <JUMP_HOST> <JUMP_PORT> \
  <搜索词>
```

> `<skill_dir>` 动态解析：SKILL.md 文件所在的目录即为 skill 根目录，无需硬编码绝对路径。

## 脚本：scripts/connect.exp

```
用法: connect.exp <跳板密钥> <跳板用户> <跳板地址> <跳板端口> <搜索词> [精确主机名]
```

自动化流程：
1. SSH 登录 JumpServer 堡垒机
2. 等待 `Opt>`，发送搜索词
3. 如果出现 `[Host]>`（多个结果），发送精确主机名
4. 检测终端类型：交互式终端 → `interact` 保持会话；非 TTY（Bash 工具） → 显示成功信息后退出

## 依赖

- 需要安装 `expect`（macOS 预装）
- SSH 密钥必须可访问
