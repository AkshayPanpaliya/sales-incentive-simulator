"""
db_utils.py
-----------
Database utilities for the Sales Incentive Compensation Simulator.

Provides functions to:
* Create a SQLite database via SQLAlchemy.
* Execute DDL scripts (create_tables.sql, analytical_views.sql).
* Bulk-load Pandas DataFrames into database tables.
* Execute ad-hoc SQL queries and return results as DataFrames.

SQLite is used as the embedded analytical store so the project has no external
database dependency, making local development and CI/CD frictionless.

The schema is intentionally compatible with the SQL scripts under ``sql/``
so that the same DDL can be pointed at PostgreSQL with minimal changes.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import pandas as pd
from sqlalchemy import create_engine, event, text
from sqlalchemy.engine import Engine

from src.logger import get_logger

logger = get_logger(__name__)

# ---------------------------------------------------------------------------
# Module-level path helpers
# ---------------------------------------------------------------------------
_PROJECT_ROOT: Path = Path(__file__).resolve().parent.parent
_SQL_DIR: Path = _PROJECT_ROOT / "sql"


def get_engine(db_path: str = "data/sales_incentive.db") -> Engine:
    """
    Create (or reuse) a SQLAlchemy engine connected to a SQLite database.

    Parameters
    ----------
    db_path : str
        Path to the SQLite file.  The parent directory is created if absent.
        Defaults to ``data/sales_incentive.db``.

    Returns
    -------
    sqlalchemy.engine.Engine
    """
    os.makedirs(os.path.dirname(db_path) if os.path.dirname(db_path) else ".", exist_ok=True)
    connection_string = f"sqlite:///{db_path}"
    engine = create_engine(connection_string, echo=False)

    # Enable WAL mode and foreign-key enforcement on every new connection.
    @event.listens_for(engine, "connect")
    def _set_pragmas(dbapi_connection: Any, _connection_record: Any) -> None:
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA journal_mode=WAL;")
        cursor.execute("PRAGMA foreign_keys=ON;")
        cursor.execute("PRAGMA synchronous=NORMAL;")
        cursor.close()

    logger.info("SQLAlchemy engine created for '%s'.", db_path)
    return engine


def create_tables(engine: Engine) -> None:
    """
    Execute ``sql/create_tables.sql`` against *engine*.

    The DDL uses ``CREATE TABLE IF NOT EXISTS`` so this function is idempotent.

    Parameters
    ----------
    engine : Engine
        Connected SQLAlchemy engine.
    """
    ddl_path = _SQL_DIR / "create_tables.sql"
    _execute_sql_file(engine, ddl_path, "create_tables.sql")
    logger.info("Database tables created (or already exist).")


def load_dataframes(
    engine: Engine,
    data_dict: dict[str, pd.DataFrame],
) -> None:
    """
    Bulk-load a dictionary of DataFrames into the corresponding database tables.

    The DataFrame key must match the target table name exactly.  Existing rows
    are replaced on each load (``if_exists="replace"``), making this function
    suitable for full refreshes.

    Parameters
    ----------
    engine : Engine
        Connected SQLAlchemy engine.
    data_dict : dict[str, pd.DataFrame]
        Mapping of ``table_name → DataFrame``.
    """
    for table_name, df in data_dict.items():
        df.to_sql(
            name=table_name,
            con=engine,
            if_exists="replace",
            index=False,
            chunksize=1_000,
        )
        logger.info(
            "Loaded %d rows into table '%s'.", len(df), table_name
        )


def execute_views(engine: Engine) -> None:
    """
    Execute ``sql/analytical_views.sql`` to (re-)create all analytical views.

    Parameters
    ----------
    engine : Engine
        Connected SQLAlchemy engine.
    """
    views_path = _SQL_DIR / "analytical_views.sql"
    _execute_sql_file(engine, views_path, "analytical_views.sql")
    logger.info("Analytical views created (or already exist).")


def query_to_df(engine: Engine, sql: str) -> pd.DataFrame:
    """
    Execute an arbitrary SELECT statement and return results as a DataFrame.

    Parameters
    ----------
    engine : Engine
        Connected SQLAlchemy engine.
    sql : str
        Valid SQL SELECT statement.

    Returns
    -------
    pd.DataFrame
        Query results; empty DataFrame if the query returns no rows.
    """
    with engine.connect() as conn:
        df = pd.read_sql_query(text(sql), conn)
    logger.debug("Query returned %d rows.", len(df))
    return df


def setup_database(
    data_dict: dict[str, pd.DataFrame],
    db_path: str = "data/sales_incentive.db",
) -> Engine:
    """
    Full database setup: create engine, tables, load data, and create views.

    This is the single convenience function that orchestrates the entire
    database lifecycle and is called from ``main.py``.

    Parameters
    ----------
    data_dict : dict[str, pd.DataFrame]
        DataFrames to load.  Expected keys: ``"sales_reps"``,
        ``"transactions"``, ``"incentive_plan"``, ``"calendar"``.
        An optional ``"payout_results"`` key is also handled.
    db_path : str
        Path to the SQLite file.

    Returns
    -------
    Engine
        The configured SQLAlchemy engine (kept open for downstream queries).
    """
    logger.info("=== Setting up SQLite database at '%s' ===", db_path)

    engine = get_engine(db_path)
    create_tables(engine)
    load_dataframes(engine, data_dict)
    execute_views(engine)

    logger.info("=== Database setup complete. ===")
    return engine


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _execute_sql_file(engine: Engine, path: Path, label: str) -> None:
    """
    Read a ``.sql`` file and execute each statement individually.

    SQLite's Python driver does not support ``executescript`` inside an open
    transaction managed by SQLAlchemy, so we split on ``;`` and execute
    statements one at a time.

    Parameters
    ----------
    engine : Engine
        Connected SQLAlchemy engine.
    path : Path
        Absolute path to the SQL file.
    label : str
        Human-readable label used only for log messages.
    """
    if not path.exists():
        raise FileNotFoundError(
            f"SQL file not found: '{path}'.  "
            "Ensure the sql/ directory is present in the project root."
        )

    sql_text = path.read_text(encoding="utf-8")

    # Split on semicolons; strip leading/trailing whitespace from each segment.
    # A segment is only skipped if it has no non-comment, non-blank lines,
    # i.e. every non-empty line starts with "--".
    def _is_executable(segment: str) -> bool:
        lines = [ln.strip() for ln in segment.splitlines()]
        return any(ln and not ln.startswith("--") for ln in lines)

    statements = [
        stmt.strip()
        for stmt in sql_text.split(";")
        if _is_executable(stmt)
    ]

    with engine.begin() as conn:
        for stmt in statements:
            if stmt:
                conn.execute(text(stmt))

    logger.debug("Executed %d statement(s) from '%s'.", len(statements), label)
