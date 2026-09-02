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

from functools import wraps
from typing import Any, List, Optional
from fastapi import HTTPException, status
import json
import uuid
from datetime import datetime

from sqlalchemy import delete, func, insert, select, update
from safir_monitoring.types_ import Fn
from oslo_log import log as logging

from .base import DB, inject_db
from .models import Notification, AlarmRule
from safir_monitoring import schemas


LOG = logging.getLogger(__name__)


def check_db_connected(fn: Fn) -> Any:
    @wraps(fn)
    async def wrapper(*args: Any, **kwargs: Any) -> Any:
        await inject_db()
        db = DB.get()
        assert db is not None, "Database is not connected."
        return await fn(*args, **kwargs)
    return wrapper

# ==================== Notification Operations ====================

@check_db_connected
async def list_notifications(project_id: str) -> Any:
    query = select(Notification).where(
        Notification.c.project_id == project_id,
        Notification.c.deleted_at == None
    )
    db = DB.get()
    async with db.transaction():
        result = await db.fetch_all(query)
    return result


@check_db_connected
async def get_notification(notification_id: str) -> Any:
    query = select(Notification).where(
        Notification.c.id == notification_id,
        Notification.c.deleted_at == None
    )
    db = DB.get()
    async with db.transaction():
        result = await db.fetch_one(query)

    if result is None:
        raise HTTPException(
            status_code=404,
            detail="Notification not found with id {}".format(notification_id)
        )
    return result


@check_db_connected
async def create_notification(project_id: str, name: str, type: str, value: str) -> Any:
    notification_id = str(uuid.uuid4())
    db = DB.get()
    async with db.transaction():
        query = insert(Notification)
        await db.execute(query, {
            "id": notification_id,
            "project_id": project_id,
            "name": name,
            "type": type,
            "value": value
        })
    return notification_id


@check_db_connected
async def update_notification(
    notification_id: str,
    name: Optional[str] = None,
    type: Optional[str] = None,
    value: Optional[str] = None
) -> Any:
    query = select(Notification).where(
        Notification.c.id == notification_id,
        Notification.c.deleted_at == None
    )
    db = DB.get()
    async with db.transaction():
        result = await db.fetch_one(query)

        if result is None:
            raise HTTPException(
                status_code=404,
                detail="Notification not found with id {}".format(notification_id)
            )

        update_data = {}
        if name is not None:
            update_data["name"] = name
        if type is not None:
            update_data["type"] = type
        if value is not None:
            update_data["value"] = value

        if update_data:
            query = update(Notification).where(Notification.c.id == notification_id)
            await db.execute(query, update_data)


@check_db_connected
async def delete_notification(notification_id: str) -> Any:
    query = update(Notification).where(
        Notification.c.id == notification_id,
        Notification.c.deleted_at == None
    )
    db = DB.get()
    async with db.transaction():
        result = await db.execute(query, {"deleted_at": datetime.utcnow()})

    if result == 0:
        raise HTTPException(
            status_code=404,
            detail="Notification not found with id {}".format(notification_id)
        )
    return None


@check_db_connected
async def is_notification_in_use(notification_id: str, project_id: str) -> bool:
    """Check if notification is used by any alarm rules"""
    db = DB.get()
    async with db.transaction():
        query = select(func.count()).select_from(AlarmRule).where(
            AlarmRule.c.project_id == project_id,
            AlarmRule.c.notification_ids.contains(f'"{notification_id}"')
        )
        result = await db.fetch_val(query)
        return result > 0


@check_db_connected
async def get_all_notifications_by_project() -> dict:
    """Get all notifications grouped by project_id"""
    query = select(Notification).where(Notification.c.deleted_at == None)
    db = DB.get()
    async with db.transaction():
        notifications = await db.fetch_all(query)

    result = {}
    for notif in notifications:
        project_id = notif["project_id"]
        if project_id not in result:
            result[project_id] = []

        result[project_id].append({
            "id": notif["id"],
            "name": notif["name"],
            "type": notif["type"],    # email | sms
            "value": notif["value"]   # email adresi veya telefon numarası
        })

    return result


# ==================== Alarm Rule Operations ====================

@check_db_connected
async def list_alarm_rules(project_id: str, enabled: Optional[bool] = None) -> Any:
    query = select(AlarmRule).where(
        AlarmRule.c.project_id == project_id
    )

    if enabled is not None:
        query = query.where(AlarmRule.c.enabled == enabled)

    db = DB.get()
    async with db.transaction():
        result = await db.fetch_all(query)

    parsed_result = []
    for row in result:
        row_dict = dict(row)
        if row_dict.get("labels"):
            row_dict["labels"] = json.loads(row_dict["labels"])
        if row_dict.get("annotations"):
            row_dict["annotations"] = json.loads(row_dict["annotations"])
        if row_dict.get("notification_ids"):
            row_dict["notification_ids"] = json.loads(row_dict["notification_ids"])
        parsed_result.append(row_dict)

    return parsed_result


@check_db_connected
async def get_alarm_rule(alarm_rule_id: str) -> Any:
    query = select(AlarmRule).where(
        AlarmRule.c.id == alarm_rule_id
    )
    db = DB.get()
    async with db.transaction():
        result = await db.fetch_one(query)

    if result is None:
        raise HTTPException(
            status_code=404,
            detail="Alarm rule not found with id {}".format(alarm_rule_id)
        )

    row_dict = dict(result)
    if row_dict.get("labels"):
        row_dict["labels"] = json.loads(row_dict["labels"])
    if row_dict.get("annotations"):
        row_dict["annotations"] = json.loads(row_dict["annotations"])
    if row_dict.get("notification_ids"):
        row_dict["notification_ids"] = json.loads(row_dict["notification_ids"])

    return row_dict


@check_db_connected
async def create_alarm_rule(
    project_id: str,
    rule_name: str,
    expr: str,
    notification_ids: List[str],
    rule_group: str = "default",
    for_duration: Optional[str] = None,
    severity: Optional[str] = None,
    labels: Optional[dict] = None,
    annotations: Optional[dict] = None,
    inject_project_id: bool = True,
    enabled: bool = True
) -> Any:
    db = DB.get()
    async with db.transaction():
        existing = await db.fetch_one(
            select(AlarmRule.c.id).where(
                AlarmRule.c.project_id == project_id,
                AlarmRule.c.rule_name == rule_name
            )
        )
        if existing is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Alarm rule with name '{rule_name}' already exists in this project"
            )

    alarm_rule_id = str(uuid.uuid4())
    async with db.transaction():
        query = insert(AlarmRule)
        await db.execute(query, {
            "id": alarm_rule_id,
            "project_id": project_id,
            "rule_name": rule_name,
            "rule_group": rule_group,
            "expr": expr,
            "for_duration": for_duration,
            "severity": severity,
            "labels": json.dumps(labels) if labels else None,
            "annotations": json.dumps(annotations) if annotations else None,
            "notification_ids": json.dumps(notification_ids),
            "inject_project_id": inject_project_id,
            "enabled": enabled
        })
    return alarm_rule_id


@check_db_connected
async def update_alarm_rule(
    alarm_rule_id: str,
    rule_name: Optional[str] = None,
    rule_group: Optional[str] = None,
    expr: Optional[str] = None,
    for_duration: Optional[str] = None,
    severity: Optional[str] = None,
    labels: Optional[dict] = None,
    annotations: Optional[dict] = None,
    notification_ids: Optional[List[str]] = None,
    inject_project_id: Optional[bool] = None,
    enabled: Optional[bool] = None
) -> Any:
    query = select(AlarmRule).where(
        AlarmRule.c.id == alarm_rule_id
    )

    db = DB.get()
    async with db.transaction():
        result = await db.fetch_one(query)

        if result is None:
            raise HTTPException(
                status_code=404,
                detail="Alarm rule not found with id {}".format(alarm_rule_id)
            )

        update_data = {}
        if rule_name is not None:
            update_data["rule_name"] = rule_name
        if rule_group is not None:
            update_data["rule_group"] = rule_group
        if expr is not None:
            update_data["expr"] = expr
        if for_duration is not None:
            update_data["for_duration"] = for_duration
        if severity is not None:
            update_data["severity"] = severity
        if labels is not None:
            update_data["labels"] = json.dumps(labels)
        if annotations is not None:
            update_data["annotations"] = json.dumps(annotations)
        if notification_ids is not None:
            update_data["notification_ids"] = json.dumps(notification_ids)
        if enabled is not None:
            update_data["enabled"] = enabled
        if inject_project_id is not None:
            update_data["inject_project_id"] = inject_project_id 

        if update_data:
            query = update(AlarmRule).where(AlarmRule.c.id == alarm_rule_id)
            await db.execute(query, update_data)


@check_db_connected
async def delete_alarm_rule(alarm_rule_id: str) -> Any:
    query = delete(AlarmRule).where(AlarmRule.c.id == alarm_rule_id)
    db = DB.get()
    async with db.transaction():
        result = await db.execute(query)

    if result == 0:
        raise HTTPException(
            status_code=404,
            detail="Alarm rule not found with id {}".format(alarm_rule_id)
        )
    return None


@check_db_connected
async def toggle_alarm_rule(alarm_rule_id: str, enabled: bool) -> Any:
    query = update(AlarmRule).where(
        AlarmRule.c.id == alarm_rule_id
    )
    db = DB.get()
    async with db.transaction():
        result = await db.execute(query, {"enabled": enabled})

    if result == 0:
        raise HTTPException(
            status_code=404,
            detail="Alarm rule not found with id {}".format(alarm_rule_id)
        )
    return None