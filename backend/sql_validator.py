"""
Guards against destructive or unsafe SQL before anything touches the
database. This is the "SQL Validation" step in the system workflow diagram.

Strategy (defense in depth):
1. Parse with sqlparse and confirm exactly one statement.
2. Confirm the statement type is SELECT (read-only).
3. Reject if any blocked keyword appears anywhere in the raw text.
4. Enforce a row limit by appending LIMIT if the query doesn't have one.
"""
import sqlparse
from .config import settings


class UnsafeSQLError(Exception):
    pass


def validate_sql(sql: str) -> str:
    sql = sql.strip().rstrip(";")

    statements = sqlparse.parse(sql)
    if len(statements) != 1:
        raise UnsafeSQLError("Only a single SQL statement is allowed.")

    stmt = statements[0]
    stmt_type = stmt.get_type()
    if stmt_type not in ("SELECT", "UNKNOWN"):
        # UNKNOWN catches WITH ... SELECT (CTEs), which sqlparse mis-tags
        raise UnsafeSQLError(f"Only read-only SELECT queries are allowed (got {stmt_type}).")

    upper_sql = sql.upper()
    first_token = upper_sql.strip().split()[0] if upper_sql.strip() else ""
    if first_token not in settings.ALLOWED_SQL_KEYWORDS:
        raise UnsafeSQLError("Query must start with SELECT or WITH.")

    for bad_word in settings.BLOCKED_SQL_KEYWORDS:
        if re_word_boundary_match(bad_word, upper_sql):
            raise UnsafeSQLError(f"Blocked keyword detected: {bad_word}")

    if "LIMIT" not in upper_sql:
        sql = f"{sql} LIMIT {settings.MAX_ROWS_RETURNED}"

    return sql + ";"


def re_word_boundary_match(word: str, text: str) -> bool:
    import re
    return re.search(rf"\b{re.escape(word)}\b", text) is not None
