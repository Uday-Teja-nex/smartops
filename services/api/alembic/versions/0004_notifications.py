"""Notification channels with per-workspace rules and a delivery outbox."""
from alembic import op
import sqlalchemy as sa

revision = '0004'
down_revision = '0003'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'notification_channels',
        sa.Column('id', sa.String(80), primary_key=True),
        sa.Column('org_id', sa.String(80), sa.ForeignKey('organizations.id'), nullable=False),
        sa.Column('kind', sa.String(16), nullable=False),
        sa.Column('name', sa.String(120), nullable=False),
        sa.Column('enabled', sa.Boolean(), nullable=False),
        sa.Column('config', sa.JSON(), nullable=False),
        sa.Column('min_severity', sa.String(16), nullable=False),
        sa.Column('categories', sa.JSON(), nullable=False),
        sa.Column('active_hours', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index('ix_notification_channels_org_id', 'notification_channels', ['org_id'])
    op.create_table(
        'notification_deliveries',
        sa.Column('id', sa.String(80), primary_key=True),
        sa.Column('org_id', sa.String(80), sa.ForeignKey('organizations.id'), nullable=False),
        sa.Column('incident_id', sa.String(80), sa.ForeignKey('incidents.id'), nullable=True),
        sa.Column('channel_id', sa.String(80),
                  sa.ForeignKey('notification_channels.id', ondelete='CASCADE'), nullable=False),
        sa.Column('status', sa.String(16), nullable=False),
        sa.Column('attempts', sa.Integer(), nullable=False),
        sa.Column('last_error', sa.String(500), nullable=True),
        sa.Column('next_attempt_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('sent_at', sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint('incident_id', 'channel_id', name='uq_delivery_incident_channel'),
    )
    op.create_index('ix_notification_deliveries_org_id', 'notification_deliveries', ['org_id'])
    op.create_index('ix_notification_deliveries_incident_id', 'notification_deliveries', ['incident_id'])
    op.create_index('ix_notification_deliveries_status', 'notification_deliveries', ['status'])
    op.create_index('ix_notification_deliveries_next_attempt_at', 'notification_deliveries', ['next_attempt_at'])


def downgrade():
    op.drop_table('notification_deliveries')
    op.drop_table('notification_channels')
