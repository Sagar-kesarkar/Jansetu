"""Add anonymous quota and duplicate records without changing existing cases."""
from alembic import op
import sqlalchemy as sa

revision = 'd7a1_submission_guard'
down_revision = '9d37f737e7ed'
branch_labels = None
depends_on = None


def upgrade():
    from app.services.submission_guard import ReporterLock, SubmissionAttempt
    connection = op.get_bind()
    ReporterLock.__table__.create(connection, checkfirst=True)
    SubmissionAttempt.__table__.create(connection, checkfirst=True)
    inspector = sa.inspect(connection)
    if 'submission_guard_id' not in {c['name'] for c in inspector.get_columns('citizen_requests')}:
        op.add_column('citizen_requests', sa.Column('submission_guard_id', sa.String(64), nullable=True))
    if 'ix_citizen_requests_submission_guard_id' not in {i['name'] for i in inspector.get_indexes('citizen_requests')}:
        op.create_index('ix_citizen_requests_submission_guard_id', 'citizen_requests', ['submission_guard_id'])


def downgrade():
    raise RuntimeError('Quota history is durable. Restore a verified backup to roll back this migration.')
