"""
Alembic migrations env.py — MongoDB-aware no-op stub.

The platform uses MongoDB (Motor) which is schema-less; traditional
Alembic SQL migrations do not apply. This file exists so the repo
structure is conventional and Alembic's CLI doesn't error if invoked.

For MongoDB schema evolution (adding indexes, renaming fields) use:
  python -c "from shared.database.session import create_tables; import asyncio; asyncio.run(create_tables())"
or run the gateway startup which calls create_tables() automatically.
"""

from __future__ import annotations

import os
import sys
from logging.config import fileConfig

# ─── Alembic boilerplate (no SQL engine needed for MongoDB) ───────────────────

try:
    from alembic import context
    config = context.config
    if config.config_file_name is not None:
        fileConfig(config.config_file_name)
except Exception:
    pass  # Alembic not installed — fine, this file is a stub


def run_migrations_offline() -> None:
    """Run placeholder migration in offline mode."""
    print("[alembic/env.py] MongoDB platform — no SQL migrations to run.")


def run_migrations_online() -> None:
    """Run placeholder migration in online mode."""
    print("[alembic/env.py] MongoDB platform — no SQL migrations to run.")
    print("Use shared.database.base.create_all_indexes() to manage collection indexes.")


if __name__ == "__main__":
    try:
        if context.is_offline_mode():  # type: ignore[name-defined]
            run_migrations_offline()
        else:
            run_migrations_online()
    except NameError:
        run_migrations_online()
