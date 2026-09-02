# Copyright 2021 99cloud
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

from __future__ import annotations

from sqlalchemy import Column, MetaData, String, Table, Boolean, Text, DateTime, Float, Integer, BigInteger, UniqueConstraint
from sqlalchemy.sql import func

METADATA = MetaData()

Notification = Table(
    "notifications",
    METADATA,
    Column("id", String(36), primary_key=True, nullable=False),
    Column("project_id", String(255), nullable=False, index=True),
    Column("name", String(255), nullable=False),
    Column("type", String(50), nullable=False),    # email | webhook
    Column("value", String(255), nullable=False),  # email adresi veya webhook URL
    Column("created_at", DateTime, nullable=False, server_default=func.now()),
    Column("updated_at", DateTime, nullable=False, server_default=func.now(), onupdate=func.now()),
    Column("deleted_at", DateTime, nullable=True, index=True),
)

AlarmRule = Table(
    "alarm_rules",
    METADATA,
    Column("id", String(36), primary_key=True, nullable=False),
    Column("project_id", String(255), nullable=False, index=True),
    Column("rule_name", String(255), nullable=False),
    Column("rule_group", String(255), nullable=False, server_default='default'),
    Column("expr", Text, nullable=False),
    Column("for_duration", String(50), nullable=True),
    Column("severity", String(50), nullable=True),
    Column("labels", Text, nullable=True),
    Column("annotations", Text, nullable=True),
    Column("notification_ids", Text, nullable=False),
    Column("inject_project_id", Boolean, nullable=False, server_default='1'),
    Column("enabled", Boolean, nullable=False, server_default='1'),
    Column("created_at", DateTime, nullable=False, server_default=func.now()),
    Column("updated_at", DateTime, nullable=False, server_default=func.now(), onupdate=func.now()),
    Column("deleted_at", DateTime, nullable=True, index=True),
)

VmMetricsHourly = Table(
    "vm_metrics_hourly",
    METADATA,
    Column("id", BigInteger, primary_key=True, autoincrement=True),
    Column("instance_id", String(64), nullable=False, index=True),
    Column("instance_name", String(255), nullable=True),
    Column("project_id", String(64), nullable=True, index=True),
    Column("hostname", String(255), nullable=True),
    Column("timestamp", DateTime, nullable=False, index=True),
    Column("avg_cpu", Float, nullable=True),
    Column("max_cpu", Float, nullable=True),
    Column("avg_memory", Float, nullable=True),
    Column("max_memory", Float, nullable=True),
    Column("disk_io_bytes_sec", Float, nullable=True),
    Column("net_io_bytes_sec", Float, nullable=True),
    Column("allocated_vcpu", Integer, nullable=True),
    Column("allocated_memory_bytes", BigInteger, nullable=True),
    UniqueConstraint("instance_id", "timestamp", name="uq_vm_instance_timestamp"),
)

HostMetricsHourly = Table(
    "host_metrics_hourly",
    METADATA,
    Column("id", BigInteger, primary_key=True, autoincrement=True),
    Column("instance", String(64), nullable=False, index=True),
    Column("nodename", String(255), nullable=True, index=True),
    Column("timestamp", DateTime, nullable=False, index=True),
    Column("cpu_percent", Float, nullable=True),
    Column("memory_percent", Float, nullable=True),
    Column("disk_percent", Float, nullable=True),
    Column("memory_total_bytes", BigInteger, nullable=True),
    Column("disk_total_bytes", BigInteger, nullable=True),
    Column("placement_vcpu_used", Float, nullable=True),
    Column("placement_vcpu_total", Float, nullable=True),
    Column("placement_memory_used_mb", Float, nullable=True),
    Column("placement_memory_total_mb", Float, nullable=True),
    Column("placement_disk_used_gb", Float, nullable=True),
    Column("placement_disk_total_gb", Float, nullable=True),
    UniqueConstraint("instance", "timestamp", name="uq_host_instance_timestamp"),
)

ReportSchedule = Table(
    "report_schedules",
    METADATA,
    Column("id", String(36), primary_key=True, nullable=False),
    Column("project_id", String(64), nullable=False, index=True),
    Column("name", String(255), nullable=False),
    Column("email", String(255), nullable=False),
    Column("day_of_week", String(20), nullable=False),
    Column("hour", Integer, nullable=False),
    Column("minute", Integer, nullable=False, server_default='0'),
    Column("timezone", String(50), nullable=False, server_default='Europe/Istanbul'),
    Column("enabled", Boolean, nullable=False, server_default='1'),
    Column("last_run", DateTime, nullable=True),
    Column("created_at", DateTime, nullable=False, server_default=func.now()),
    Column("updated_at", DateTime, nullable=False, server_default=func.now(), onupdate=func.now()),
    Column("deleted_at", DateTime, nullable=True, index=True),
)