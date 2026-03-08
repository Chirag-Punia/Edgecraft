"""add AI assistant tables: chat_sessions, chat_messages, customer_reviews,
review_insights, demand_forecasts, pricing_recommendations

Revision ID: 0003
Revises: 0002
Create Date: 2026-03-08

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '0003'
down_revision: Union[str, Sequence[str], None] = '0002'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # -- chat_sessions --
    op.create_table(
        'chat_sessions',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('seller_id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('title', sa.String(500), nullable=True),
        sa.Column('language', sa.String(10), server_default='en'),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(['seller_id'], ['sellers.id']),
        sa.ForeignKeyConstraint(['user_id'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_chat_sessions_seller_id', 'chat_sessions', ['seller_id'])
    op.create_index('ix_chat_sessions_user_id', 'chat_sessions', ['user_id'])

    # -- chat_messages --
    op.create_table(
        'chat_messages',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('session_id', sa.Integer(), nullable=False),
        sa.Column('role', sa.String(20), nullable=False),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('report_spec', sa.JSON(), nullable=True),
        sa.Column('report_data', sa.JSON(), nullable=True),
        sa.Column('metadata', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(['session_id'], ['chat_sessions.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_chat_messages_session_id', 'chat_messages', ['session_id'])

    # -- customer_reviews --
    op.create_table(
        'customer_reviews',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('marketplace_account_id', sa.Integer(), nullable=False),
        sa.Column('external_review_id', sa.String(100), nullable=False),
        sa.Column('asin', sa.String(20), nullable=True),
        sa.Column('seller_sku', sa.String(100), nullable=True),
        sa.Column('rating', sa.Integer(), nullable=False),
        sa.Column('title', sa.String(500), nullable=True),
        sa.Column('body', sa.Text(), nullable=True),
        sa.Column('reviewer_name', sa.String(255), nullable=True),
        sa.Column('review_date', sa.DateTime(), nullable=False),
        sa.Column('verified_purchase', sa.Boolean(), server_default='0'),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(['marketplace_account_id'], ['marketplace_accounts.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('marketplace_account_id', 'external_review_id', name='uq_review_account_extid'),
    )
    op.create_index('ix_customer_reviews_marketplace_account_id', 'customer_reviews', ['marketplace_account_id'])
    op.create_index('ix_customer_reviews_review_date', 'customer_reviews', ['review_date'])

    # -- review_insights --
    op.create_table(
        'review_insights',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('marketplace_account_id', sa.Integer(), nullable=False),
        sa.Column('asin', sa.String(20), nullable=False),
        sa.Column('insight_date', sa.Date(), nullable=False),
        sa.Column('avg_sentiment', sa.Numeric(3, 2), nullable=True),
        sa.Column('positive_count', sa.Integer(), server_default='0'),
        sa.Column('negative_count', sa.Integer(), server_default='0'),
        sa.Column('neutral_count', sa.Integer(), server_default='0'),
        sa.Column('top_topics', sa.JSON(), nullable=True),
        sa.Column('top_complaints', sa.JSON(), nullable=True),
        sa.Column('top_praises', sa.JSON(), nullable=True),
        sa.Column('summary', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(['marketplace_account_id'], ['marketplace_accounts.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('marketplace_account_id', 'asin', 'insight_date', name='uq_insight_account_asin_date'),
    )
    op.create_index('ix_review_insights_marketplace_account_id', 'review_insights', ['marketplace_account_id'])
    op.create_index('ix_review_insights_asin', 'review_insights', ['asin'])

    # -- demand_forecasts --
    op.create_table(
        'demand_forecasts',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('marketplace_account_id', sa.Integer(), nullable=False),
        sa.Column('asin', sa.String(20), nullable=False),
        sa.Column('seller_sku', sa.String(100), nullable=True),
        sa.Column('forecast_date', sa.Date(), nullable=False),
        sa.Column('horizon_days', sa.Integer(), nullable=False),
        sa.Column('predicted_units', sa.Integer(), nullable=False),
        sa.Column('confidence_lower', sa.Integer(), nullable=True),
        sa.Column('confidence_upper', sa.Integer(), nullable=True),
        sa.Column('velocity_7d', sa.Numeric(10, 2), nullable=True),
        sa.Column('velocity_30d', sa.Numeric(10, 2), nullable=True),
        sa.Column('days_of_stock', sa.Integer(), nullable=True),
        sa.Column('stockout_risk', sa.Boolean(), server_default='0'),
        sa.Column('method', sa.String(50), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(['marketplace_account_id'], ['marketplace_accounts.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('marketplace_account_id', 'asin', 'forecast_date', 'horizon_days', name='uq_forecast_account_asin_date_horizon'),
    )
    op.create_index('ix_demand_forecasts_marketplace_account_id', 'demand_forecasts', ['marketplace_account_id'])

    # -- pricing_recommendations --
    op.create_table(
        'pricing_recommendations',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('marketplace_account_id', sa.Integer(), nullable=False),
        sa.Column('asin', sa.String(20), nullable=False),
        sa.Column('seller_sku', sa.String(100), nullable=True),
        sa.Column('recommendation_date', sa.Date(), nullable=False),
        sa.Column('current_price', sa.Numeric(10, 2), nullable=True),
        sa.Column('buybox_price', sa.Numeric(10, 2), nullable=True),
        sa.Column('lowest_competitor', sa.Numeric(10, 2), nullable=True),
        sa.Column('recommended_price', sa.Numeric(10, 2), nullable=True),
        sa.Column('price_action', sa.String(50), nullable=True),
        sa.Column('margin_impact_pct', sa.Numeric(5, 2), nullable=True),
        sa.Column('reasoning', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(['marketplace_account_id'], ['marketplace_accounts.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('marketplace_account_id', 'asin', 'recommendation_date', name='uq_pricing_rec_account_asin_date'),
    )
    op.create_index('ix_pricing_recommendations_marketplace_account_id', 'pricing_recommendations', ['marketplace_account_id'])


def downgrade() -> None:
    op.drop_table('pricing_recommendations')
    op.drop_table('demand_forecasts')
    op.drop_table('review_insights')
    op.drop_table('customer_reviews')
    op.drop_table('chat_messages')
    op.drop_table('chat_sessions')
