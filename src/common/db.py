"""PostgreSQL connection helpers (SQLAlchemy + psycopg2)."""
from contextlib import contextmanager
from functools import lru_cache

from sqlalchemy import create_engine, text
from sqlalchemy.engine import URL, Engine

from src.common import config


@lru_cache(maxsize=1)
def get_engine() -> Engine:
    url = URL.create(
        "postgresql+psycopg2",
        username=config.DB_USER,
        password=config.DB_PASSWORD or None,
        host=config.DB_HOST,
        port=config.DB_PORT,
        database=config.DB_NAME,
    )
    # gssencmode=disable: libpq's Kerberos/GSS probe hangs inside forked processes on macOS
    # (e.g. Airflow task runners). GSS encryption is not used for this database anyway.
    return create_engine(url, pool_pre_ping=True, future=True, connect_args={"gssencmode": "disable"})


@contextmanager
def transaction():
    with get_engine().begin() as conn:
        yield conn


def execute_sql_file(path) -> None:
    with open(path) as f:
        sql = f.read()
    with transaction() as conn:
        conn.exec_driver_sql(sql)


def run(sql: str, **params):
    with transaction() as conn:
        return conn.execute(text(sql), params)


def truncate(conn, table: str) -> None:
    conn.exec_driver_sql(f"TRUNCATE TABLE {table} RESTART IDENTITY CASCADE")
