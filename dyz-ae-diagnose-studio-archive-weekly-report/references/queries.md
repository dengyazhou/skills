# SQL 全集（经 ta1 在 studio.db 上执行）

> 统一用 `created_at >= '<since> 00:00:00'` 圈本周（since 为本周一 YYYY-MM-DD）。
> 变量：`W` = `a.created_at >= '<since> 00:00:00'`。
> mcp 识别（自动化通道）：归档 dir_path 前缀匹配 `tasks.archive_path` 且 `tasks.source='mcp'`。
> 以下 SQL 均为只读 SELECT。

## 0. 总数
```sql
SELECT COUNT(*) total_all,
       SUM(created_at >= '<since> 00:00:00') week_cnt
FROM archives;
```
注意：`archives` 别名为 a 时请写 `FROM archives a`，勿裸用 `a.`。

## 1. 全量状态分布（含自动化）
```sql
SELECT COALESCE(NULLIF(TRIM(outcome), ''), 'none') st, COUNT(*) n
FROM archives WHERE created_at >= '<since> 00:00:00'
GROUP BY st;
```

## 2. mcp 自动化归档（应始终是 code-diagnose 模板问答）
```sql
SELECT a.id, a.skill_id, a.created_at
FROM archives a JOIN tasks t ON a.dir_path LIKE t.archive_path || '%'
WHERE a.created_at >= '<since> 00:00:00' AND t.source = 'mcp'
ORDER BY a.created_at;
```

## 3. 人工 skill × outcome（排除 mcp）
```sql
SELECT a.skill_id,
       COALESCE(NULLIF(TRIM(a.outcome), ''), 'none') st,
       COUNT(*) n
FROM archives a
WHERE a.created_at >= '<since> 00:00:00'
  AND a.id NOT IN (
    SELECT a2.id FROM archives a2
    JOIN tasks t ON a2.dir_path LIKE t.archive_path || '%'
    WHERE a2.created_at >= '<since> 00:00:00' AND t.source = 'mcp')
GROUP BY a.skill_id, st ORDER BY a.skill_id;
```

## 4. 人工每人 × 状态
```sql
SELECT u.username,
       COALESCE(NULLIF(TRIM(a.outcome), ''), 'none') st,
       COUNT(*) n
FROM archives a JOIN users u ON u.id = a.owner_id
WHERE a.created_at >= '<since> 00:00:00'
  AND a.id NOT IN (<同 3 的 mcp 子查询>)
GROUP BY u.username, st ORDER BY u.username;
```

## 5. 人工 unresolved 明细（含优化状态 fix_*，列随 ta1 迁移已存在）
```sql
SELECT u.username, a.skill_id, a.created_at,
       COALESCE(a.fix_status, '') fix,
       COALESCE(a.fix_optimized_at, '') fixat,
       substr(COALESCE(a.fix_note, ''), 1, 30) note
FROM archives a JOIN users u ON u.id = a.owner_id
WHERE a.created_at >= '<since> 00:00:00'
  AND a.id NOT IN (<mcp 子查询>)
  AND TRIM(a.outcome) = 'unresolved'
ORDER BY a.skill_id, a.created_at;
```
解读：`fix_status='optimized'` ⇒ 该未定位会话已在 Web Studio 标记「已优化」（fix_optimized_at 为标记时间），即「未定位中已优化 Y」的取值来源。

## 6. 人工未标记明细（cluster 归一：脏值 ID:→Garena、空→-）
```sql
SELECT u.username, a.created_at, a.skill_id,
       CASE WHEN COALESCE(NULLIF(TRIM(a.cluster), ''), '') = 'ID:' THEN 'Garena'
            WHEN COALESCE(NULLIF(TRIM(a.cluster), ''), '') = '' THEN '-'
            ELSE a.cluster END cl,
       substr(replace(replace(a.question, char(10), ' '), char(13), ' '), 1, 70) q
FROM archives a JOIN users u ON u.id = a.owner_id
WHERE a.created_at >= '<since> 00:00:00'
  AND a.id NOT IN (<mcp 子查询>)
  AND COALESCE(NULLIF(TRIM(a.outcome), ''), 'none') = 'none'
ORDER BY a.created_at;
```

## 7. 人工 cluster 分布（同样归一 ID:→Garena；空→(空)）
```sql
SELECT CASE WHEN COALESCE(NULLIF(TRIM(a.cluster), ''), '') = 'ID:' THEN 'Garena'
            WHEN COALESCE(NULLIF(TRIM(a.cluster), ''), '') = '' THEN '(空)'
            ELSE a.cluster END cl,
       COUNT(*) n
FROM archives a
WHERE a.created_at >= '<since> 00:00:00'
  AND a.id NOT IN (<mcp 子查询>)
GROUP BY cl ORDER BY n DESC;
```

## 派生指标
- 人工总数 = Σ(3) = Σ(4)；人工 = week_cnt − mcp 数；
- 状态占比（人工）= resolved/unresolved/none 各 / 人工总数；
- 结论标记率 = (resolved + unresolved) / 人工总数；
- skill「未定位 X · 已优化 Y」：X = 该 skill unresolved 数（自查询 3），Y = 该 skill 中查询 5 里 fix='optimized' 条数。
