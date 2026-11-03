from alembic import op
from services.api.db import RateLimit
revision='0002'
down_revision='0001'
branch_labels=None
depends_on=None
def upgrade():RateLimit.__table__.create(op.get_bind(),checkfirst=True)
def downgrade():RateLimit.__table__.drop(op.get_bind(),checkfirst=True)
