"""empty message

Revision ID: ec325180dd7f
Revises: 4ca757e5543b
Create Date: 2024-01-10 12:27:04.890778

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'ec325180dd7f'
down_revision = '4ca757e5543b'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_table('lobby',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('owner_id', sa.Integer(), nullable=True),
    sa.Column('game_id', sa.Integer(), nullable=True),
    sa.Column('description', sa.JSON(), nullable=True),
    sa.ForeignKeyConstraint(['game_id'], ['game.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['owner_id'], ['user.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('session', schema=None) as batch_op:
        batch_op.add_column(sa.Column('replay', sa.JSON(), nullable=True))
        batch_op.add_column(sa.Column('created_by', sa.Integer(), nullable=True))
        batch_op.create_foreign_key(None, 'user', ['created_by'], ['id'])
        batch_op.drop_column('record')

    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('session', schema=None) as batch_op:
        batch_op.add_column(sa.Column('record', postgresql.JSON(astext_type=sa.Text()), autoincrement=False, nullable=True))
        batch_op.drop_constraint(None, type_='foreignkey')
        batch_op.drop_column('created_by')
        batch_op.drop_column('replay')

    op.drop_table('lobby')
    # ### end Alembic commands ###
