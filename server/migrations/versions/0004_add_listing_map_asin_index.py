"""Add composite index on listing_map(marketplace_account_id, asin) for AI product name lookups.

Revision ID: 0004
Revises: 0003
"""
from alembic import op

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_index(
        "ix_listing_map_account_asin",
        "listing_map",
        ["marketplace_account_id", "asin"],
    )


def downgrade() -> None:
    op.drop_index("ix_listing_map_account_asin", table_name="listing_map")
