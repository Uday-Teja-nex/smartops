"""Revocable sign-in sessions with rotating refresh tokens."""
from alembic import op
import sqlalchemy as sa

revision = '0003'
down_revision = '0002'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'auth_sessions',
        sa.Column('id', sa.String(80), primary_key=True),
        sa.Column('org_id', sa.String(80), sa.ForeignKey('organizations.id'), nullable=False),
        sa.Column('user_id', sa.String(80), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('refresh_hash', sa.String(64), nullable=False, unique=True),
        sa.Column('previous_refresh_hash', sa.String(64), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('last_used_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('revoked_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('revoked_reason', sa.String(40), nullable=True),
    )
    op.create_index('ix_auth_sessions_org_id', 'auth_sessions', ['org_id'])
    op.create_index('ix_auth_sessions_user_id', 'auth_sessions', ['user_id'])
    op.create_index('ix_auth_sessions_previous_refresh_hash', 'auth_sessions', ['previous_refresh_hash'])


def downgrade():
    op.drop_table('auth_sessions')
