# JumpServer 连接配置

## SSH 参数（客户堡垒机）

| 参数 | 值 | 说明 |
|------|-----|------|
| `JUMP_SSH_KEY` | `/Users/thinkingdata-yazhou/.ssh/dyz_customer.jumpserver.pem` | SSH 私钥路径 |
| `JUMP_USER` | `dengyazhou` | JumpServer 登录用户名 |
| `JUMP_HOST` | `jumpserver-customer.thinkingdata.cn` | JumpServer 堡垒机地址 |
| `JUMP_PORT` | `2222` | SSH 端口 |

## SSH 参数（内部堡垒机）

| 参数 | 值 | 说明 |
|------|-----|------|
| `JUMP_SSH_KEY` | `/Users/thinkingdata-yazhou/.ssh/dyz_inner.jumpserver.pem` | SSH 私钥路径 |
| `JUMP_USER` | `dengyazhou` | JumpServer 登录用户名 |
| `JUMP_HOST` | `jumpserver-inner-v4.thinkingdata.cn` | JumpServer 堡垒机地址 |
| `JUMP_PORT` | `2222` | SSH 端口 |
