"""add llm_providers

Revision ID: a1b2c3d4e5f6
Revises: 76c1bd883902
Create Date: 2026-06-27 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, Sequence[str], None] = '76c1bd883902'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table('llm_providers',
    sa.Column('id', sa.String(length=36), nullable=False),
    sa.Column('provider_type', sa.String(length=30), nullable=False),
    sa.Column('display_name', sa.String(length=100), nullable=False),
    sa.Column('base_url', sa.String(length=255), nullable=True),
    sa.Column('models', sa.JSON(), nullable=False),
    sa.Column('is_active', sa.Boolean(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('llm_providers', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_llm_providers_provider_type'), ['provider_type'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table('llm_providers', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_llm_providers_provider_type'))

    op.drop_table('llm_providers')
