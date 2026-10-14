from alembic import context

from app.core.db import get_engine
from app.models import Base

target_metadata = Base.metadata


def run_migrations_online() -> None:
    with get_engine().connect() as conn:
        context.configure(connection=conn, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


run_migrations_online()
