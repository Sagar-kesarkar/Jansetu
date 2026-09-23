"""SQLite for the weekend, Postgres-ready via DATABASE_URL.

Deliberate choice: a hackathon demo that depends on a managed database is one
more thing that can fail in front of judges. The engine URL is the only thing
that changes when this moves to Cloud SQL for a real deployment.
"""
from collections.abc import Generator
import logging

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import get_settings

log = logging.getLogger(__name__)

settings = get_settings()

connect_args = {"check_same_thread": False} if settings.database_url.startswith("sqlite") else {}
engine = create_engine(settings.database_url, connect_args=connect_args, future=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    from app.db import models, financial_models  # noqa: F401  (registers tables)
    Base.metadata.create_all(bind=engine)
    _add_missing_columns()
    _add_missing_indexes()


def _add_missing_columns() -> None:
    """Additive-only schema catch-up for databases created by an earlier version.

    `create_all` creates missing *tables* but silently ignores missing *columns*
    on tables that already exist. Anyone who seeded before `citizen_requests.status`
    was introduced would otherwise get `OperationalError: no such column` on their
    first console request, with nothing pointing at the cause.

    Alembic is the right answer for a system with real migrations. For additive
    columns that all carry a server default, one guarded ALTER is far less
    machinery to explain and cannot lose data: nothing is dropped, renamed or
    retyped, and a column that is already present is skipped.
    """
    from sqlalchemy import inspect, text

    inspector = inspect(engine)
    existing_tables = set(inspector.get_table_names())

    for table in Base.metadata.sorted_tables:
        if table.name not in existing_tables:
            continue  # create_all just made it, with every column
        present = {c["name"] for c in inspector.get_columns(table.name)}
        for column in table.columns:
            if column.name in present:
                continue
            if column.server_default is None and not column.nullable:
                # Would need a backfill decision that belongs to a human.
                log.warning(
                    "%s.%s is missing and has no server default — add it by hand or re-seed",
                    table.name, column.name,
                )
                continue
            ddl = f"ALTER TABLE {table.name} ADD COLUMN {column.name} {column.type.compile(engine.dialect)}"
            if column.server_default is not None:
                default = column.server_default.arg
                # A bare string default has to be quoted or SQLite reads "NEW" as
                # an identifier and fails with a syntax error.
                literal = f"'{default}'" if isinstance(default, str) else str(default)
                ddl += f" DEFAULT {literal}"
            if not column.nullable:
                ddl += " NOT NULL"
            log.info("migrating: %s", ddl)
            with engine.begin() as conn:
                conn.execute(text(ddl))


def _add_missing_indexes() -> None:
    """The other half of the catch-up above: indexes declared on a model but
    absent from a database created before they were.

    `_add_missing_columns` cannot carry them. SQLite's `ALTER TABLE ADD COLUMN`
    explicitly forbids a UNIQUE constraint in the column definition, so
    `citizen_requests.track_token` — whose uniqueness is what stops two citizens
    being handed the same tracking reference — would arrive on an existing
    database as an ordinary nullable column with no enforcement at all, and the
    guarantee documented in `services/tracking.py` would quietly be false.

    Creating it as a separate UNIQUE INDEX is not a workaround, it is how
    SQLAlchemy already renders `unique=True, index=True`: the constraint lives in
    the index either way, so a fresh database and a migrated one end up identical.
    Pre-existing rows hold NULL, and SQLite counts NULLs as distinct in a unique
    index, so the index can be built before the backfill rather than after.
    """
    from sqlalchemy import inspect

    inspector = inspect(engine)
    existing_tables = set(inspector.get_table_names())

    for table in Base.metadata.sorted_tables:
        if table.name not in existing_tables:
            continue  # create_all just made it, with every index
        present = {ix["name"] for ix in inspector.get_indexes(table.name)}
        columns = {c["name"] for c in inspector.get_columns(table.name)}
        for index in table.indexes:
            if index.name in present:
                continue
            if not {c.name for c in index.columns}.issubset(columns):
                continue  # its column was skipped above; nothing to index yet
            log.info(
                "migrating: CREATE %sINDEX %s ON %s",
                "UNIQUE " if index.unique else "", index.name, table.name,
            )
            try:
                index.create(bind=engine, checkfirst=True)
            except Exception as exc:  # noqa: BLE001
                # A unique index can legitimately fail on a database that already
                # holds duplicates. Refusing to boot would be the wrong trade in a
                # demo; a warning naming the index is what a human needs to fix it.
                log.warning("could not create index %s: %s", index.name, exc)
