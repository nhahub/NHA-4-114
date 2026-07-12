"""initial schema: cameras, events, alerts, zones

Revision ID: 0001_initial
Revises:
Create Date: 2026-06-18 00:00:00.000000

Creates the base tables that previously existed only via init_db()'s
create_all(). This is the missing base revision referenced by
0002_add_users (down_revision = "0001_initial"). (C8)
"""
from alembic import op
import sqlalchemy as sa

revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── cameras ────────────────────────────────────────────────────────────────
    op.create_table(
        "cameras",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("source_type", sa.String(length=16), nullable=False),
        sa.Column("source_url", sa.String(length=512), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=True, server_default=sa.text("true")),
        sa.Column("worker_task_id", sa.String(length=64), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=True,
            server_default=sa.text("now()"),
        ),
    )

    # ── events ───────────────────────────────────────────────────────────────────
    op.create_table(
        "events",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("camera_id", sa.Integer(), nullable=False),
        sa.Column("event_type", sa.String(length=64), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column(
            "timestamp",
            sa.DateTime(timezone=True),
            nullable=True,
            server_default=sa.text("now()"),
        ),
    )
    op.create_index(op.f("ix_events_camera_id"), "events", ["camera_id"], unique=False)
    op.create_index(op.f("ix_events_timestamp"), "events", ["timestamp"], unique=False)

    # ── alerts ───────────────────────────────────────────────────────────────────
    op.create_table(
        "alerts",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("camera_id", sa.Integer(), nullable=False),
        sa.Column("type", sa.String(length=64), nullable=False),
        sa.Column("severity", sa.String(length=16), nullable=False, server_default="low"),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("resolved", sa.Boolean(), nullable=True, server_default=sa.text("false")),
        sa.Column(
            "timestamp",
            sa.DateTime(timezone=True),
            nullable=True,
            server_default=sa.text("now()"),
        ),
    )
    op.create_index(op.f("ix_alerts_camera_id"), "alerts", ["camera_id"], unique=False)
    op.create_index(op.f("ix_alerts_timestamp"), "alerts", ["timestamp"], unique=False)

    # ── zones (post-C7 shape: polygon / is_active / created_at) ──────────────────
    op.create_table(
        "zones",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("camera_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=64), nullable=False),
        sa.Column("polygon", sa.JSON(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("current_occupancy", sa.Integer(), nullable=True, server_default="0"),
        sa.Column("threshold", sa.Integer(), nullable=True, server_default="5"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=True,
            server_default=sa.text("now()"),
        ),
    )
    op.create_index(op.f("ix_zones_camera_id"), "zones", ["camera_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_zones_camera_id"), table_name="zones")
    op.drop_table("zones")
    op.drop_index(op.f("ix_alerts_timestamp"), table_name="alerts")
    op.drop_index(op.f("ix_alerts_camera_id"), table_name="alerts")
    op.drop_table("alerts")
    op.drop_index(op.f("ix_events_timestamp"), table_name="events")
    op.drop_index(op.f("ix_events_camera_id"), table_name="events")
    op.drop_table("events")
    op.drop_table("cameras")
