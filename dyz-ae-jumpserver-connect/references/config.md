# JumpServer 连接配置

> ⚠️ 本文件含**明文密码**，会随仓库提交并推送到远端（`github.com:dengyazhou/skills.git`）。请确认该仓库为私有仓库。

## 登录方式

| 方式 | 账号 | 凭据来源 | 状态 |
|------|------|----------|------|
| **账号密码** | `shuxiaozhi` | 各段 `JUMP_PASSWORD` | **默认** |
| 密钥 | `dengyazhou` | 各段 `JUMP_SSH_KEY` | 备选（兼容保留） |

## 客户/私有化：jumpserver-customer.thinkingdata.cn

```bash
ssh shuxiaozhi@jumpserver-customer.thinkingdata.cn -p 2222
# 提示 password 时输入：pLZ471naEryfsxOJSlti
```

| 参数 | 值 | 说明 |
|------|-----|------|
| `JUMP_USER` | `shuxiaozhi` | 登录用户名 |
| `JUMP_PASSWORD` | `pLZ471naEryfsxOJSlti` | 登录密码 |
| `JUMP_HOST` | `jumpserver-customer.thinkingdata.cn` | 堡垒机地址 |
| `JUMP_PORT` | `2222` | SSH 端口 |
| `JUMP_SSH_KEY`（备选） | `/Users/thinkingdata-yazhou/.ssh/dyz_customer.jumpserver.pem` | 密钥登录私钥（此时 `JUMP_USER=dengyazhou`） |

## 内部/SaaS：jumpserver-inner-v4.thinkingdata.cn

```bash
ssh shuxiaozhi@jumpserver-inner-v4.thinkingdata.cn -p 2222
# 提示 password 时输入：pLZ471naEryfsxOJSlti
```

| 参数 | 值 | 说明 |
|------|-----|------|
| `JUMP_USER` | `shuxiaozhi` | 登录用户名 |
| `JUMP_PASSWORD` | `pLZ471naEryfsxOJSlti` | 登录密码 |
| `JUMP_HOST` | `jumpserver-inner-v4.thinkingdata.cn` | 堡垒机地址 |
| `JUMP_PORT` | `2222` | SSH 端口 |
| `JUMP_SSH_KEY`（备选） | `/Users/thinkingdata-yazhou/.ssh/dyz_inner.jumpserver.pem` | 密钥登录私钥（此时 `JUMP_USER=dengyazhou`） |
