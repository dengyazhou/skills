#!/usr/bin/env bash
# =============================================================================
# selftest.sh — dyz-ae-jumpserver-connect 自测（改完 skill 后跑一次，回归功能）
#
# 用法:
#   ./selftest.sh              # 全部用例（离线 + 内部 + 客户），约 2-3 分钟
#   ./selftest.sh --offline    # 只跑离线用例（参数校验，秒级、不联网）
#   ./selftest.sh --quick      # 离线 + 内部堡垒机（跳过客户，省时间）
#
# 环境变量可覆盖测试目标（默认指向测试机，勿指向生产客户机）:
#   INNER_SEARCH     内部堡叠机资产搜索词   (默认 运维-技术交付测试机-腾讯云-刘路)
#   CUSTOMER_SEARCH  客户堡垒机资产搜索词   (默认 豹亮)
#
# 断言依据：connect.exp 的退出码（0/1/2/3）与关键输出行。
# 密码与密钥路径从 references/config.md 解析，脚本内不硬编码凭据。
#
# 退出码: 0 全部通过 | 1 有用例失败
# =============================================================================
set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SKILL_DIR="$(dirname "$SCRIPT_DIR")"
CONNECT="$SCRIPT_DIR/connect.exp"
CONFIG_MD="$SKILL_DIR/references/config.md"

INNER_SEARCH="${INNER_SEARCH:-运维-技术交付测试机-腾讯云-刘路}"
CUSTOMER_SEARCH="${CUSTOMER_SEARCH:-豹亮}"

MODE="all"
case "${1:-}" in
    --offline) MODE="offline" ;;
    --quick)   MODE="quick" ;;
    --all|"")  MODE="all" ;;
    -h|--help) sed -n '2,20p' "$0"; exit 0 ;;
    *) echo "未知参数: $1（可用 --offline | --quick | --all）" >&2; exit 1 ;;
esac

# ----- 解析 config.md 凭据（单一来源，避免脚本内硬编码）-----
cfg_get() {  # cfg_get <段落关键字> <KEY>
    awk -v sec="$1" -v key="$2" '
        $0 ~ /^## / { in_sec = (index($0, sec) > 0); next }
        in_sec && index($0, "`" key "`") > 0 {
            n = split($0, p, "|")
            # markdown 表格: | KEY | VALUE | 说明 |  → 按 | 切分后 p[1] 为空串，值在 p[3]
            if (n >= 4) {
                v = p[3]
                gsub(/^[ \t]*`/, "", v)
                gsub(/`[ \t]*$/, "", v)
                gsub(/^[ \t]+|[ \t]+$/, "", v)
                print v
                exit
            }
        }
    ' "$CONFIG_MD"
}

if [ ! -f "$CONFIG_MD" ]; then
    echo "找不到配置: $CONFIG_MD" >&2
    exit 1
fi

C_USER="$(cfg_get 客户 JUMP_USER)"
C_PASS="$(cfg_get 客户 JUMP_PASSWORD)"
C_HOST="$(cfg_get 客户 JUMP_HOST)"
C_PORT="$(cfg_get 客户 JUMP_PORT)"
C_KEY="$(cfg_get 客户 JUMP_SSH_KEY)"

I_USER="$(cfg_get 内部 JUMP_USER)"
I_PASS="$(cfg_get 内部 JUMP_PASSWORD)"
I_HOST="$(cfg_get 内部 JUMP_HOST)"
I_PORT="$(cfg_get 内部 JUMP_PORT)"
I_KEY="$(cfg_get 内部 JUMP_SSH_KEY)"

for v in C_USER C_PASS C_HOST C_PORT C_KEY I_USER I_PASS I_HOST I_PORT I_KEY; do
    if [ -z "${!v}" ]; then
        echo "config.md 解析失败：$v 为空（检查参考文献表格格式）" >&2
        exit 1
    fi
done

# ----- 用例框架 -----
TOTAL=0; PASSED=0
FAILED_NAMES=()

run_case() {  # run_case <名称> <期望退出码> <输出须包含...> -- <connect.exp 参数...>
    local name="$1" want_rc="$2"; shift 2
    local pats=()
    while [ $# -gt 0 ] && [ "$1" != "--" ]; do pats+=("$1"); shift; done
    [ "${1:-}" = "--" ] && shift

    TOTAL=$((TOTAL + 1))
    printf '\n[%d] %s\n' "$TOTAL" "$name"
    # 打印命令时屏蔽第 2 个参数（secret：密码或密钥路径），避免测试输出泄露凭据
    # 不用数组展开：bash 3.2 + set -u 下 "${arr[*]}" 会报 unbound variable
    local shown
    if [ $# -ge 2 ]; then
        shown="$1 <secret>"
        local i=0 a
        for a in "$@"; do
            i=$((i + 1))
            if [ "$i" -gt 2 ]; then shown="$shown $a"; fi
        done
    else
        shown="$*"
    fi
    printf '    $ expect connect.exp %s\n' "$shown"

    local start=$SECONDS
    local out rc
    out="$(expect "$CONNECT" "$@" 2>&1)"; rc=$?
    local cost=$((SECONDS - start))

    local ok=1 detail=""
    if [ "$rc" != "$want_rc" ]; then
        ok=0; detail="退出码 $rc ≠ 期望 $want_rc"
    fi
    # 注意：bash 3.2 + set -u 下空数组展开会报 unbound，故先判长度
    if [ "${#pats[@]}" -gt 0 ]; then
        local p
        for p in "${pats[@]}"; do
            if ! printf '%s' "$out" | grep -qF -- "$p"; then
                ok=0
                detail="${detail:+$detail; }输出缺少「$p」"
            fi
        done
    fi

    if [ "$ok" = 1 ]; then
        PASSED=$((PASSED + 1))
        printf '    ✅ PASS (%ds)\n' "$cost"
    else
        FAILED_NAMES+=("$name")
        printf '    ❌ FAIL (%ds) — %s\n' "$cost" "$detail"
        printf '    --- 实际输出（末 25 行）---\n'
        printf '%s\n' "$out" | tail -25 | sed 's/^/    | /'
        printf '    --------------------------\n'
    fi
}

# =============================================================================
# 一、离线用例（不联网，校验脚本自身健壮性）
# =============================================================================
echo "=========================================="
echo " 一、离线用例（参数校验，不联网）"
echo "=========================================="

run_case "无参数 → 打印 Usage 并退出码 1" 1 "Usage: connect.exp" -- 
run_case "非法 auth 值 → 报错退出码 1" 1 "必须是 key 或 password" -- bogus x "$I_USER" "$I_HOST" "$I_PORT" "$INNER_SEARCH"
run_case "参数不足（缺搜索词） → 退出码 1" 1 "Usage: connect.exp" -- password "$I_PASS" "$I_USER" "$I_HOST"

if [ "$MODE" = "offline" ]; then
    echo
    echo "(--offline：跳过联网用例)"
else
    # =========================================================================
    # 二、内部堡垒机
    # =========================================================================
    echo
    echo "=========================================="
    echo " 二、内部堡垒机 ($I_HOST)"
    echo "=========================================="

    run_case "密码登录 (shuxiaozhi) → 连通测试机" 0 \
        "Connected to target host successfully" "账号 $I_USER" "认证方式 password" -- \
        password "$I_PASS" "$I_USER" "$I_HOST" "$I_PORT" "$INNER_SEARCH"

    run_case "密钥登录 (dengyazhou) → 连通测试机" 0 \
        "Connected to target host successfully" "认证方式 key" -- \
        key "$I_KEY" dengyazhou "$I_HOST" "$I_PORT" "$INNER_SEARCH"

    if [ "$MODE" = "quick" ]; then
        echo
        echo "(--quick：跳过客户堡垒机用例)"
    else
        # =====================================================================
        # 三、客户堡垒机（含 ID> 账号选择场景）
        # =====================================================================
        echo
        echo "=========================================="
        echo " 三、客户堡垒机 ($C_HOST)"
        echo "=========================================="

        run_case "密码登录 (shuxiaozhi) → 连通 $CUSTOMER_SEARCH" 0 \
            "Connected to target host successfully" "认证方式 password" -- \
            password "$C_PASS" "$C_USER" "$C_HOST" "$C_PORT" "$CUSTOMER_SEARCH"

        run_case "密钥登录 (dengyazhou) → ID> 自动选 readonly" 0 \
            "Connected to target host successfully" "readonly" -- \
            key "$C_KEY" dengyazhou "$C_HOST" "$C_PORT" "$CUSTOMER_SEARCH"

        run_case "密钥登录 + 显式账号 ID=2 → 进入 root" 0 \
            "Connected to target host successfully" "[root@" -- \
            key "$C_KEY" dengyazhou "$C_HOST" "$C_PORT" "$CUSTOMER_SEARCH" "2"
    fi
fi

# =============================================================================
# 汇总
# =============================================================================
echo
echo "=========================================="
printf ' 汇总: %d/%d 通过' "$PASSED" "$TOTAL"
if [ "$PASSED" != "$TOTAL" ]; then
    printf '  （失败: %s）' "${FAILED_NAMES[*]}"
fi
echo
echo "=========================================="

[ "$PASSED" = "$TOTAL" ] || exit 1
exit 0
