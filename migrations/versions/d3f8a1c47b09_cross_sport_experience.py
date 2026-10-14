"""cross_sport_experience

Gives a fighter profile an owning user, so one person competing in several
disciplines can be recognised as the same fighter, and adds a table for
experience declared by a coach rather than fought on the platform. Together
these feed the matchmaker's transfer credit — without them a boxer with ten
bouts enters kickboxing scored as a debutant.

Revision ID: d3f8a1c47b09
Revises: a7c41d9b52e3
Create Date: 2026-08-26 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = 'd3f8a1c47b09'
down_revision = 'a7c41d9b52e3'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('fighters', schema=None) as batch_op:
        batch_op.add_column(sa.Column('user_id', sa.Integer(), nullable=True))
        batch_op.create_index('ix_fighters_user_id', ['user_id'])
        batch_op.create_foreign_key(
            'fk_fighters_user_id', 'users', ['user_id'], ['id'],
            ondelete='SET NULL',
        )

    # Backfill ownership from the existing single account link. Written as a
    # correlated subquery rather than UPDATE..FROM so it runs on SQLite too.
    op.execute("""
        UPDATE fighters
        SET user_id = (
            SELECT u.id FROM users u
            WHERE u.fighter_id = fighters.id
              AND u.fighter_sport = fighters.sport
            LIMIT 1
        )
        WHERE user_id IS NULL
    """)

    op.create_table(
        'fighter_prior_experience',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('fighter_id', sa.Integer(), nullable=False),
        sa.Column('sport', sa.String(length=20), nullable=False),
        sa.Column('wins', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('losses', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('draws', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('last_bout_date', sa.String(length=20), nullable=True),
        sa.Column('note', sa.String(length=255), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.CheckConstraint('wins   >= 0', name='ck_prior_wins'),
        sa.CheckConstraint('losses >= 0', name='ck_prior_losses'),
        sa.CheckConstraint('draws  >= 0', name='ck_prior_draws'),
        sa.ForeignKeyConstraint(['fighter_id'], ['fighters.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('fighter_id', 'sport', name='uq_prior_fighter_sport'),
    )
    with op.batch_alter_table('fighter_prior_experience', schema=None) as batch_op:
        batch_op.create_index('ix_fighter_prior_experience_fighter_id', ['fighter_id'])


def downgrade():
    with op.batch_alter_table('fighter_prior_experience', schema=None) as batch_op:
        batch_op.drop_index('ix_fighter_prior_experience_fighter_id')
    op.drop_table('fighter_prior_experience')

    with op.batch_alter_table('fighters', schema=None) as batch_op:
        batch_op.drop_constraint('fk_fighters_user_id', type_='foreignkey')
        batch_op.drop_index('ix_fighters_user_id')
        batch_op.drop_column('user_id')
