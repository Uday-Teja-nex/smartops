"""Persist evidence URL issuance audits."""
from alembic import op
import sqlalchemy as sa

revision = '0002'
down_revision = '0001'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'evidence_access',
        sa.Column('id', sa.String(80), primary_key=True),
        sa.Column('org_id', sa.String(80), sa.ForeignKey('organizations.id'), nullable=False),
        sa.Column('evidence_id', sa.String(80), sa.ForeignKey('evidence_items.id'), nullable=False),
        sa.Column('actor_id', sa.String(80), nullable=False),
        sa.Column('actor_role', sa.String(32), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index('ix_evidence_access_org_id', 'evidence_access', ['org_id'])
    op.create_index('ix_evidence_access_evidence_id', 'evidence_access', ['evidence_id'])


def downgrade():
    op.drop_table('evidence_access')
