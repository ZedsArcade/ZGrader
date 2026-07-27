"""account security columns, email normalisation, subscriptions

Revision ID: b3d61f8a92c7
Revises: f7a2c9e04b18
Create Date: 2026-07-26 00:00:00.000000

Three things at once, because they all touch `users`:

1. Columns for password reset, token revocation, terms acceptance and the
   Stripe customer handle.
2. Email normalisation. Emails were compared case-sensitively, so
   `Bob@x.com` and `bob@x.com` were different accounts and someone who
   registered with capitals could not log in in lowercase. Existing rows are
   lowercased and a functional unique index stops it recurring -- but if two
   rows would collide, this migration ABORTS rather than guessing which
   account to keep. That needs a human.
3. Existing users are marked verified. Verification is enforced from now on,
   and the verification email was never actually sent before this release, so
   without this every current account would be locked out of submitting.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b3d61f8a92c7'
down_revision: Union[str, None] = 'f7a2c9e04b18'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('users', sa.Column('verification_token_expires_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('users', sa.Column('password_reset_token', sa.String(length=64), nullable=True))
    op.add_column('users', sa.Column('password_reset_expires_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('users', sa.Column('token_version', sa.Integer(), nullable=False, server_default='1'))
    op.add_column('users', sa.Column('terms_accepted_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('users', sa.Column('terms_version', sa.String(length=20), nullable=True))
    op.add_column('users', sa.Column('marketing_consent', sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column('users', sa.Column('last_login_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('users', sa.Column('stripe_customer_id', sa.String(length=64), nullable=True))
    op.create_unique_constraint('uq_users_password_reset_token', 'users', ['password_reset_token'])
    op.create_unique_constraint('uq_users_stripe_customer_id', 'users', ['stripe_customer_id'])

    # Stop before doing damage if lowercasing would merge two real accounts.
    conn = op.get_bind()
    clashes = conn.execute(
        sa.text(
            "SELECT lower(email) AS e, count(*) FROM users "
            "GROUP BY lower(email) HAVING count(*) > 1"
        )
    ).fetchall()
    if clashes:
        listed = ", ".join(row[0] for row in clashes)
        raise RuntimeError(
            "Cannot normalise emails to lowercase: these addresses exist more than once "
            f"with different capitalisation: {listed}. Merge or delete the duplicates by "
            "hand, then re-run the migration."
        )
    op.execute("UPDATE users SET email = lower(email) WHERE email <> lower(email)")
    op.execute("CREATE UNIQUE INDEX ix_users_email_lower ON users (lower(email))")

    # Verification is enforced from this release; the verification email was
    # never sent before it, so everyone existing is grandfathered in.
    op.execute("UPDATE users SET is_verified = true WHERE is_verified = false")

    op.create_table(
        'subscriptions',
        sa.Column('user_id', sa.Uuid(), nullable=False),
        sa.Column('stripe_subscription_id', sa.String(length=64), nullable=True),
        sa.Column('plan', sa.String(length=64), nullable=False),
        sa.Column(
            'status',
            sa.Enum('active', 'trialing', 'past_due', 'canceled', 'incomplete', name='subscription_status'),
            nullable=False,
        ),
        sa.Column('current_period_end', sa.DateTime(timezone=True), nullable=True),
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('stripe_subscription_id'),
    )
    op.create_index('ix_subscriptions_user_id', 'subscriptions', ['user_id'])


def downgrade() -> None:
    op.drop_index('ix_subscriptions_user_id', table_name='subscriptions')
    op.drop_table('subscriptions')
    op.execute('DROP TYPE IF EXISTS subscription_status')
    op.execute('DROP INDEX IF EXISTS ix_users_email_lower')
    op.drop_constraint('uq_users_stripe_customer_id', 'users', type_='unique')
    op.drop_constraint('uq_users_password_reset_token', 'users', type_='unique')
    for column in (
        'stripe_customer_id',
        'last_login_at',
        'marketing_consent',
        'terms_version',
        'terms_accepted_at',
        'token_version',
        'password_reset_expires_at',
        'password_reset_token',
        'verification_token_expires_at',
    ):
        op.drop_column('users', column)
