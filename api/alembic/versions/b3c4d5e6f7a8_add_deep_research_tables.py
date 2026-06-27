"""add deep research tables

Revision ID: b3c4d5e6f7a8
Revises: a1b2c3d4e5f6
Create Date: 2026-06-27 00:01:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b3c4d5e6f7a8'
down_revision: Union[str, Sequence[str], None] = 'a1b2c3d4e5f6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table('deep_research_sessions',
    sa.Column('id', sa.String(length=36), nullable=False),
    sa.Column('account_id', sa.String(length=36), nullable=False),
    sa.Column('provider_id', sa.String(length=36), nullable=True),
    sa.Column('model', sa.String(length=100), nullable=False),
    sa.Column('title', sa.String(length=200), nullable=True),
    sa.Column('status', sa.String(length=30), nullable=False),
    sa.Column('plan', sa.JSON(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['account_id'], ['accounts.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['provider_id'], ['llm_providers.id'], ondelete='SET NULL'),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('deep_research_sessions', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_deep_research_sessions_account_id'), ['account_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_deep_research_sessions_provider_id'), ['provider_id'], unique=False)

    op.create_table('deep_research_messages',
    sa.Column('id', sa.String(length=36), nullable=False),
    sa.Column('session_id', sa.String(length=36), nullable=False),
    sa.Column('role', sa.String(length=20), nullable=False),
    sa.Column('kind', sa.String(length=20), nullable=False),
    sa.Column('content', sa.Text(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['session_id'], ['deep_research_sessions.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('deep_research_messages', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_deep_research_messages_session_id'), ['session_id'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table('deep_research_messages', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_deep_research_messages_session_id'))

    op.drop_table('deep_research_messages')
    with op.batch_alter_table('deep_research_sessions', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_deep_research_sessions_provider_id'))
        batch_op.drop_index(batch_op.f('ix_deep_research_sessions_account_id'))

    op.drop_table('deep_research_sessions')
