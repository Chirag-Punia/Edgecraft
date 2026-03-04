"""add etl pipeline tables

Revision ID: 0001
Revises:
Create Date: 2026-03-04 19:47:53.558100

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0001'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # --- Existing tables ---
    op.create_table(
        'sellers',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('business_name', sa.String(255), nullable=False),
        sa.Column('business_type', sa.String(100), nullable=True),
        sa.Column('primary_category', sa.String(100), nullable=True),
        sa.Column('gst_number', sa.String(20), nullable=True),
        sa.Column('city', sa.String(100), nullable=True),
        sa.Column('state', sa.String(100), nullable=True),
        sa.Column('onboarding_completed', sa.Boolean(), server_default='0'),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )

    op.create_table(
        'users',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('email', sa.String(255), nullable=False),
        sa.Column('hashed_password', sa.String(255), nullable=True),
        sa.Column('full_name', sa.String(255), nullable=False),
        sa.Column('is_email_verified', sa.Boolean(), server_default='0'),
        sa.Column('auth_provider', sa.String(20), server_default='local'),
        sa.Column('google_id', sa.String(255), nullable=True),
        sa.Column('role', sa.String(20), server_default='owner'),
        sa.Column('seller_id', sa.Integer(), sa.ForeignKey('sellers.id'), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('email'),
        sa.UniqueConstraint('google_id'),
    )
    op.create_index('ix_users_email', 'users', ['email'])

    op.create_table(
        'email_otps',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('code', sa.String(6), nullable=False),
        sa.Column('expires_at', sa.DateTime(), nullable=False),
        sa.Column('is_used', sa.Boolean(), server_default='0'),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_email_otps_user_id', 'email_otps', ['user_id'])

    op.create_table(
        'marketplace_accounts',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('seller_id', sa.Integer(), sa.ForeignKey('sellers.id'), nullable=False),
        sa.Column('marketplace', sa.String(50), nullable=False),
        sa.Column('status', sa.String(30), server_default='pending', nullable=False),
        sa.Column('credentials_encrypted', sa.Text(), nullable=True),
        sa.Column('last_sync_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_marketplace_accounts_seller_id', 'marketplace_accounts', ['seller_id'])

    # --- New ETL tables ---
    op.create_table(
        'sync_runs',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('marketplace_account_id', sa.Integer(), sa.ForeignKey('marketplace_accounts.id'), nullable=False),
        sa.Column('sync_type', sa.String(30), nullable=False),
        sa.Column('status', sa.String(20), server_default='running', nullable=False),
        sa.Column('started_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column('completed_at', sa.DateTime(), nullable=True),
        sa.Column('records_fetched', sa.Integer(), server_default='0'),
        sa.Column('records_upserted', sa.Integer(), server_default='0'),
        sa.Column('error_log', sa.Text(), nullable=True),
        sa.Column('cursor_state', sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_sync_runs_marketplace_account_id', 'sync_runs', ['marketplace_account_id'])

    op.create_table(
        'product_master',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('seller_id', sa.Integer(), sa.ForeignKey('sellers.id'), nullable=False),
        sa.Column('name', sa.String(500), nullable=False),
        sa.Column('brand', sa.String(255), nullable=True),
        sa.Column('category', sa.String(255), nullable=True),
        sa.Column('hsn_code', sa.String(20), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_product_master_seller_id', 'product_master', ['seller_id'])

    op.create_table(
        'listing_map',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('product_master_id', sa.Integer(), sa.ForeignKey('product_master.id'), nullable=True),
        sa.Column('marketplace_account_id', sa.Integer(), sa.ForeignKey('marketplace_accounts.id'), nullable=False),
        sa.Column('marketplace_sku', sa.String(100), nullable=False),
        sa.Column('asin', sa.String(20), nullable=True),
        sa.Column('fnsku', sa.String(20), nullable=True),
        sa.Column('listing_title', sa.String(500), nullable=True),
        sa.Column('listing_status', sa.String(30), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('marketplace_account_id', 'marketplace_sku', name='uq_listing_account_sku'),
    )
    op.create_index('ix_listing_map_marketplace_account_id', 'listing_map', ['marketplace_account_id'])
    op.create_index('ix_listing_map_product_master_id', 'listing_map', ['product_master_id'])

    op.create_table(
        'orders',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('marketplace_account_id', sa.Integer(), sa.ForeignKey('marketplace_accounts.id'), nullable=False),
        sa.Column('external_order_id', sa.String(100), nullable=False),
        sa.Column('marketplace', sa.String(50), server_default='amazon', nullable=False),
        sa.Column('status', sa.String(50), nullable=False),
        sa.Column('order_date', sa.DateTime(), nullable=False),
        sa.Column('fulfillment_channel', sa.String(20), nullable=True),
        sa.Column('currency', sa.String(10), server_default='INR'),
        sa.Column('total_amount', sa.Numeric(12, 2), nullable=False),
        sa.Column('shipping_amount', sa.Numeric(10, 2), server_default='0'),
        sa.Column('ship_city', sa.String(100), nullable=True),
        sa.Column('ship_state', sa.String(100), nullable=True),
        sa.Column('raw_payload', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('marketplace_account_id', 'external_order_id', name='uq_order_account_extid'),
    )
    op.create_index('ix_orders_marketplace_account_id', 'orders', ['marketplace_account_id'])
    op.create_index('ix_orders_order_date', 'orders', ['order_date'])

    op.create_table(
        'order_items',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('order_id', sa.Integer(), sa.ForeignKey('orders.id'), nullable=False),
        sa.Column('marketplace_account_id', sa.Integer(), sa.ForeignKey('marketplace_accounts.id'), nullable=False),
        sa.Column('external_order_item_id', sa.String(100), nullable=False),
        sa.Column('asin', sa.String(20), nullable=True),
        sa.Column('seller_sku', sa.String(100), nullable=True),
        sa.Column('title', sa.String(500), nullable=True),
        sa.Column('quantity_ordered', sa.Integer(), server_default='1'),
        sa.Column('quantity_shipped', sa.Integer(), server_default='0'),
        sa.Column('unit_price', sa.Numeric(10, 2), nullable=False),
        sa.Column('item_tax', sa.Numeric(10, 2), server_default='0'),
        sa.Column('item_discount', sa.Numeric(10, 2), server_default='0'),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('order_id', 'external_order_item_id', name='uq_orderitem_order_extid'),
    )
    op.create_index('ix_order_items_order_id', 'order_items', ['order_id'])
    op.create_index('ix_order_items_marketplace_account_id', 'order_items', ['marketplace_account_id'])

    op.create_table(
        'inventory_snapshots',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('marketplace_account_id', sa.Integer(), sa.ForeignKey('marketplace_accounts.id'), nullable=False),
        sa.Column('seller_sku', sa.String(100), nullable=False),
        sa.Column('asin', sa.String(20), nullable=True),
        sa.Column('fnsku', sa.String(20), nullable=True),
        sa.Column('fulfillable_quantity', sa.Integer(), server_default='0'),
        sa.Column('inbound_quantity', sa.Integer(), server_default='0'),
        sa.Column('reserved_quantity', sa.Integer(), server_default='0'),
        sa.Column('unfulfillable_quantity', sa.Integer(), server_default='0'),
        sa.Column('total_quantity', sa.Integer(), server_default='0'),
        sa.Column('snapshot_date', sa.Date(), nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('marketplace_account_id', 'seller_sku', 'snapshot_date', name='uq_inventory_account_sku_date'),
    )
    op.create_index('ix_inventory_snapshots_marketplace_account_id', 'inventory_snapshots', ['marketplace_account_id'])
    op.create_index('ix_inventory_snapshots_snapshot_date', 'inventory_snapshots', ['snapshot_date'])

    op.create_table(
        'price_snapshots',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('marketplace_account_id', sa.Integer(), sa.ForeignKey('marketplace_accounts.id'), nullable=False),
        sa.Column('asin', sa.String(20), nullable=False),
        sa.Column('seller_sku', sa.String(100), nullable=True),
        sa.Column('your_price', sa.Numeric(10, 2), nullable=True),
        sa.Column('landed_price', sa.Numeric(10, 2), nullable=True),
        sa.Column('buybox_price', sa.Numeric(10, 2), nullable=True),
        sa.Column('lowest_price', sa.Numeric(10, 2), nullable=True),
        sa.Column('is_buybox_winner', sa.Boolean(), server_default='0'),
        sa.Column('snapshot_date', sa.Date(), nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('marketplace_account_id', 'asin', 'snapshot_date', name='uq_price_account_asin_date'),
    )
    op.create_index('ix_price_snapshots_marketplace_account_id', 'price_snapshots', ['marketplace_account_id'])
    op.create_index('ix_price_snapshots_snapshot_date', 'price_snapshots', ['snapshot_date'])


def downgrade() -> None:
    op.drop_table('price_snapshots')
    op.drop_table('inventory_snapshots')
    op.drop_table('order_items')
    op.drop_table('orders')
    op.drop_table('listing_map')
    op.drop_table('product_master')
    op.drop_table('sync_runs')
    op.drop_table('marketplace_accounts')
    op.drop_table('email_otps')
    op.drop_table('users')
    op.drop_table('sellers')
