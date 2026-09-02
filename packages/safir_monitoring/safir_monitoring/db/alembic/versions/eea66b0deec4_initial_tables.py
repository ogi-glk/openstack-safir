"""Initial Tables — consolidated migration

Revision ID: eea66b0deec4
Revises:
Create Date: 2023-05-03 11:57:11.157243
"""
from alembic import op
import sqlalchemy as sa

revision = 'eea66b0deec4'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    # --- notifications ---
    op.create_table(
        "notifications",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("project_id", sa.String(length=255), nullable=False, index=True),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("type", sa.String(length=50), nullable=False),
        sa.Column("value", sa.String(length=255), nullable=False),
        sa.Column("created_at", sa.DateTime, nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime, nullable=False, server_default=sa.func.now()),
        sa.Column("deleted_at", sa.DateTime, nullable=True, index=True),
        sa.PrimaryKeyConstraint('id')
    )

    # --- alarm_rules ---
    op.create_table(
        "alarm_rules",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("project_id", sa.String(length=255), nullable=False, index=True),
        sa.Column("rule_name", sa.String(length=255), nullable=False),
        sa.Column("rule_group", sa.String(length=255), nullable=False, server_default='default'),
        sa.Column("expr", sa.Text, nullable=False),
        sa.Column("for_duration", sa.String(length=50), nullable=True),
        sa.Column("severity", sa.String(length=50), nullable=True),
        sa.Column("labels", sa.Text, nullable=True),
        sa.Column("annotations", sa.Text, nullable=True),
        sa.Column("notification_ids", sa.Text, nullable=False),
        sa.Column("inject_project_id", sa.Boolean, nullable=False, server_default='1'),
        sa.Column("enabled", sa.Boolean, nullable=False, server_default='1'),
        sa.Column("created_at", sa.DateTime, nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime, nullable=False, server_default=sa.func.now()),
        sa.Column("deleted_at", sa.DateTime, nullable=True, index=True),
        sa.PrimaryKeyConstraint('id')
    )

    # --- vm_metrics_hourly ---
    op.create_table(
        'vm_metrics_hourly',
        sa.Column('id', sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column('instance_id', sa.String(64), nullable=False, index=True),
        sa.Column('instance_name', sa.String(255), nullable=True),
        sa.Column('project_id', sa.String(64), nullable=True, index=True),
        sa.Column('hostname', sa.String(255), nullable=True),
        sa.Column('timestamp', sa.DateTime, nullable=False, index=True),
        sa.Column('avg_cpu', sa.Float, nullable=True),
        sa.Column('max_cpu', sa.Float, nullable=True),
        sa.Column('avg_memory', sa.Float, nullable=True),
        sa.Column('max_memory', sa.Float, nullable=True),
        sa.Column('disk_io_bytes_sec', sa.Float, nullable=True),
        sa.Column('net_io_bytes_sec', sa.Float, nullable=True),
        sa.Column('allocated_vcpu', sa.Integer, nullable=True),
        sa.Column('allocated_memory_bytes', sa.BigInteger, nullable=True),
        sa.UniqueConstraint('instance_id', 'timestamp', name='uq_vm_instance_timestamp'),
    )

    # --- host_metrics_hourly ---
    op.create_table(
        'host_metrics_hourly',
        sa.Column('id', sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column('instance', sa.String(64), nullable=False, index=True),
        sa.Column('nodename', sa.String(255), nullable=True, index=True),
        sa.Column('timestamp', sa.DateTime, nullable=False, index=True),
        sa.Column('cpu_percent', sa.Float, nullable=True),
        sa.Column('memory_percent', sa.Float, nullable=True),
        sa.Column('disk_percent', sa.Float, nullable=True),
        sa.Column('memory_total_bytes', sa.BigInteger, nullable=True),
        sa.Column('disk_total_bytes', sa.BigInteger, nullable=True),
        sa.Column('placement_vcpu_used', sa.Float, nullable=True),
        sa.Column('placement_vcpu_total', sa.Float, nullable=True),
        sa.Column('placement_memory_used_mb', sa.Float, nullable=True),
        sa.Column('placement_memory_total_mb', sa.Float, nullable=True),
        sa.Column('placement_disk_used_gb', sa.Float, nullable=True),
        sa.Column('placement_disk_total_gb', sa.Float, nullable=True),
        sa.UniqueConstraint('instance', 'timestamp', name='uq_host_instance_timestamp'),
    )

    # --- report_schedules ---
    op.create_table(
        'report_schedules',
        sa.Column('id', sa.String(36), primary_key=True, nullable=False),
        sa.Column('project_id', sa.String(64), nullable=False, index=True),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('email', sa.String(255), nullable=False),
        sa.Column('day_of_week', sa.String(20), nullable=False),
        sa.Column('hour', sa.Integer, nullable=False),
        sa.Column('minute', sa.Integer, nullable=False, server_default='0'),
        sa.Column('timezone', sa.String(50), nullable=False, server_default='Europe/Istanbul'),
        sa.Column('enabled', sa.Boolean, nullable=False, server_default='1'),
        sa.Column('last_run', sa.DateTime, nullable=True),
        sa.Column('created_at', sa.DateTime, nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime, nullable=False, server_default=sa.func.now()),
        sa.Column('deleted_at', sa.DateTime, nullable=True, index=True),
    )


def downgrade():
    op.drop_table('report_schedules')
    op.drop_table('host_metrics_hourly')
    op.drop_table('vm_metrics_hourly')
    op.drop_table("alarm_rules")
    op.drop_table("notifications")
