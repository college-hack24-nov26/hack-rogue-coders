"""Initial shared relational foundation and PostGIS boundaries."""
from alembic import op
from services.api.db import Base
revision='0001'
down_revision=None
branch_labels=None
depends_on=None

def upgrade():
    bind=op.get_bind()
    Base.metadata.create_all(bind)
    if bind.dialect.name=='postgresql':
        op.execute('CREATE EXTENSION IF NOT EXISTS postgis')
        op.execute('ALTER TABLE villages ADD COLUMN boundary geometry(MultiPolygon,4326)')
        op.execute('CREATE INDEX villages_boundary_gix ON villages USING gist(boundary)')
def downgrade(): Base.metadata.drop_all(op.get_bind())
