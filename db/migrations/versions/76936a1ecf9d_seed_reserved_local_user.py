"""seed reserved local user

Revision ID: 76936a1ecf9d
Revises: 55b4ca0b122d
Create Date: 2026-07-09 00:05:05.153497

Guarantees core/auth.py's LOCAL_USER_ID row exists in every environment
that has run migrations (native, Docker Compose, CI), not just ones that
happen to also run `make seed`. Without this, the native voice loop
(orchestrator/pipeline.py, which always authenticates as LOCAL_USER_ID)
hard-fails its very first conversation turn with a Postgres FK violation
on `conversations.user_id -> users.id`, since `make up`/start_stack.ps1
apply migrations but never call docker/seed.py.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '76936a1ecf9d'
down_revision: Union[str, None] = '55b4ca0b122d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

LOCAL_USER_ID = "00000000-0000-0000-0000-000000000000"
LOCAL_USER_EMAIL = "local@astra.local"


def upgrade() -> None:
    op.execute(
        sa.text(
            "INSERT INTO users (id, email, provider, provider_sub) "
            "VALUES (:id, :email, 'local', 'local') "
            "ON CONFLICT (id) DO NOTHING"
        ).bindparams(id=LOCAL_USER_ID, email=LOCAL_USER_EMAIL)
    )


def downgrade() -> None:
    op.execute(sa.text("DELETE FROM users WHERE id = :id").bindparams(id=LOCAL_USER_ID))
