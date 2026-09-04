"""MySQL 数据库检索通道（Text-to-SQL 的底座）。

职责：
  1. 用只读账号连 MySQL
  2. 接收一条 SQL，做白名单校验（只允许 SELECT）
  3. 执行查询，返回 (columns, rows, meta) 三元组
  4. 把结果格式化成 LLM 可读的文本块，供 generator 拼 context

不做：
  - 不生成 SQL（那是后续 text_to_sql.py 的活，接 LLM）
  - 不做表结构注册（那是 schema_registry.py 的活）
  - 不做自然语言路由（那是 retriever.py 决策层）

设计取舍：
  - 只读防线做两层：账号层（GRANT SELECT）+ 代码层（SQL 关键词校验）
    代码层是防 SQL 注入 LLM 幻觉，账号层是防代码 bug，缺一不可
  - MAX_ROWS 硬顶，防 `SELECT * FROM orders` 几万行撑爆 context
  - LIMIT 强制注入，即便 SQL 里没写 LIMIT 也补上
"""
import re
import time
from typing import Any

import pymysql
from pymysql.cursors import DictCursor

from .config import Config

# 允许在 SQL 里出现的动词（防 LLM 生成 INSERT/UPDATE/DELETE/DROP 等）
_ALLOWED_VERBS = {"SELECT", "WITH"}
# 高危关键词，命中直接拒绝
_FORBIDDEN_KEYWORDS = {
    "INSERT", "UPDATE", "DELETE", "DROP", "ALTER", "CREATE",
    "TRUNCATE", "REPLACE", "GRANT", "REVOKE", "SET", "CALL",
    "LOAD", "INTO OUTFILE", "INTO DUMPFILE",
}
# 简单正则：找 SQL 前几个非空白 token，判第一个是不是 SELECT/WITH
_LEADING_RE = re.compile(r"\s*(\w+)", re.IGNORECASE)


class ReadOnlyViolation(Exception):
    """试图执行非只读 SQL 时抛出。"""


class SQLResult:
    """一次 SQL 查询的结构化结果。"""

    def __init__(self, columns: list[str], rows: list[dict[str, Any]],
                 latency_ms: int, total_rows: int, sql: str):
        self.columns = columns
        self.rows = rows
        self.latency_ms = latency_ms
        self.total_rows = total_rows  # 执行返回的实际行数（可能 == len(rows)）
        self.sql = sql

    def as_context(self, limit_preview: int = 20) -> str:
        """转成 LLM 可读的文本块。

        limit_preview: 若行数超此阈值，只展示前 N 行并加省略提示。
        """
        if not self.rows:
            return f"（SQL 查询返回空结果。SQL: {self.sql}）"

        header = "\t".join(self.columns)
        lines = [f"SQL: {self.sql}", f"命中 {self.total_rows} 行（{self.latency_ms}ms）", "-", header]

        shown = self.rows[:limit_preview]
        for row in shown:
            lines.append("\t".join(
                "" if row.get(c) is None else str(row.get(c)) for c in self.columns
            ))
        if len(self.rows) > limit_preview:
            lines.append(f"...（共 {len(self.rows)} 行，已截断，只展示前 {limit_preview} 行）")
        return "\n".join(lines)


class DbRetriever:
    """MySQL 只读检索器。构造时连库，close() 时释放。"""

    def __init__(self, cfg: Config | None = None):
        self.cfg = cfg or Config()
        if not self.cfg.MYSQL_ENABLED:
            raise RuntimeError("MYSQL_ENABLED=false，DbRetriever 未启用。请在 .env 打开。")
        self._conn = self._connect()

    def _connect(self) -> pymysql.Connection:
        return pymysql.connect(
            host=self.cfg.MYSQL_HOST,
            port=self.cfg.MYSQL_PORT,
            user=self.cfg.MYSQL_USER,
            password=self.cfg.MYSQL_PASSWORD,
            database=self.cfg.MYSQL_DATABASE,
            charset=self.cfg.MYSQL_CHARSET,
            cursorclass=DictCursor,
            connect_timeout=10,
            read_timeout=30,
        )

    # ---------- 安全校验 ----------
    def _validate_sql(self, sql: str) -> str:
        """只允许单条 SELECT/WITH 语句，且不允许高危关键字。"""
        if not sql or not sql.strip():
            raise ReadOnlyViolation("空 SQL")

        s = sql.strip().rstrip(";")

        # 拒绝多语句（`;` 分隔）
        if ";" in s:
            raise ReadOnlyViolation("禁止多语句执行")

        # 检查第一个非空白 token
        m = _LEADING_RE.match(s)
        if not m:
            raise ReadOnlyViolation("无法解析 SQL 起始 token")
        first = m.group(1).upper()
        if first not in _ALLOWED_VERBS:
            raise ReadOnlyViolation(f"仅允许 {sorted(_ALLOWED_VERBS)}，实际起始 token={first}")

        # 扫描高危关键字
        upper = s.upper()
        for kw in _FORBIDDEN_KEYWORDS:
            # 用词边界（近似，MySQL 保留字之间天然有空白）
            if re.search(r"\b" + re.escape(kw) + r"\b", upper):
                raise ReadOnlyViolation(f"检测到禁止关键字: {kw}")

        return s

    def _inject_limit(self, sql: str) -> str:
        """没写 LIMIT 就补一个 MYSQL_MAX_ROWS。"""
        if re.search(r"\bLIMIT\s+\d+", sql, re.IGNORECASE):
            return sql
        return f"{sql} LIMIT {self.cfg.MYSQL_MAX_ROWS}"

    # ---------- 执行 ----------
    def execute(self, sql: str) -> SQLResult:
        """执行一条 SQL，返回结构化结果。"""
        if self.cfg.MYSQL_READ_ONLY:
            clean = self._validate_sql(sql)
        else:
            clean = sql.strip().rstrip(";")
        clean = self._inject_limit(clean)

        t0 = time.perf_counter()
        with self._conn.cursor(DictCursor) as cur:
            cur.execute(clean)
            rows = cur.fetchall()
        latency = int((time.perf_counter() - t0) * 1000)

        columns = list(rows[0].keys()) if rows else []
        return SQLResult(
            columns=columns,
            rows=rows,
            latency_ms=latency,
            total_rows=len(rows),
            sql=clean,
        )

    def health(self) -> dict:
        """连通性检查，/info 或运维可用。"""
        try:
            with self._conn.cursor(DictCursor) as cur:
                cur.execute("SELECT 1 AS ok")
                cur.fetchone()
            return {"status": "ok", "database": self.cfg.MYSQL_DATABASE,
                    "user": self.cfg.MYSQL_USER}
        except Exception as e:
            return {"status": "error", "error": str(e)}

    def close(self):
        try:
            self._conn.close()
        except Exception:
            pass
