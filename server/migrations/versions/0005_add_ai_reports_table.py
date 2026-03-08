"""add ai_reports table

Revision ID: 0005
Revises: 0004
"""
from alembic import op
import sqlalchemy as sa

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "ai_reports",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("seller_id", sa.Integer(), sa.ForeignKey("sellers.id"), nullable=False),
        sa.Column("report_type", sa.String(50), nullable=False),
        sa.Column("report_data", sa.JSON(), nullable=True),
        sa.Column("ai_narrative", sa.Text(), nullable=True),
        sa.Column("score", sa.Integer(), nullable=True),
        sa.Column("generated_at", sa.DateTime(), nullable=True),
        sa.Column("expires_at", sa.DateTime(), nullable=True),
        sa.Column("language", sa.String(5), nullable=False, server_default="en"),
        sa.Column("status", sa.String(20), nullable=False, server_default="generating"),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("seller_id", "report_type", "language", name="uq_ai_report_seller_type_lang"),
    )
    op.create_index("ix_ai_reports_seller_id", "ai_reports", ["seller_id"])


def downgrade():
    op.drop_index("ix_ai_reports_seller_id", table_name="ai_reports")
    op.drop_table("ai_reports")
