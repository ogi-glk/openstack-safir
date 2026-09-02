"""Rapor zamanlama CRUD API endpoint'leri."""

from __future__ import annotations

import uuid
from typing import Optional
from datetime import datetime

from fastapi import APIRouter, Header, Request, HTTPException, status, Query
from pydantic import BaseModel, Field
from oslo_log import log as logging

from safir_monitoring.common import policy, utils
from safir_monitoring.reporting import scheduler as report_scheduler

LOG = logging.getLogger(__name__)

router = APIRouter()


# ============================================================================
# SCHEMAS
# ============================================================================

class ReportScheduleCreate(BaseModel):
    name: str = Field(..., description="Rapor adi")
    email: str = Field(..., description="Alici email adresi")
    day_of_week: str = Field(..., description="Gun: mon, tue, wed, thu, fri, sat, sun")
    hour: int = Field(..., description="Saat (0-23)", ge=0, le=23)
    minute: int = Field(0, description="Dakika (0-59)", ge=0, le=59)
    timezone: str = Field("Europe/Istanbul", description="Timezone (orn: Europe/Istanbul, UTC)")


class ReportScheduleUpdate(BaseModel):
    name: Optional[str] = None
    email: Optional[str] = None
    day_of_week: Optional[str] = None
    hour: Optional[int] = Field(None, ge=0, le=23)
    minute: Optional[int] = Field(None, ge=0, le=59)
    timezone: Optional[str] = None
    enabled: Optional[bool] = None


class ReportScheduleResponse(BaseModel):
    id: str
    project_id: str
    name: str
    email: str
    day_of_week: str
    hour: int
    minute: int
    timezone: str
    enabled: bool
    last_run: Optional[str] = None
    created_at: Optional[str] = None


VALID_DAYS = {"mon", "tue", "wed", "thu", "fri", "sat", "sun"}


# ============================================================================
# ENDPOINTS
# ============================================================================

@router.post(
    "/reports/schedules",
    description="Create a new report schedule",
    response_model=ReportScheduleResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_schedule(
    request: Request,
    body: ReportScheduleCreate,
    X_Auth_Token: str = Header(default=None),
):
    try:
        context = await utils.req_context_from_scope(request.scope)
        policy.authorize(context, 'metric:get', {"project_id": context.project_id})

        if body.day_of_week not in VALID_DAYS:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid day_of_week: {body.day_of_week}. Valid: {VALID_DAYS}"
            )

        from safir_monitoring.db.base import DB, inject_db
        await inject_db()
        db = DB.get()

        schedule_id = str(uuid.uuid4())
        now = datetime.now()

        await db.execute(
            query="""
                INSERT INTO report_schedules (id, project_id, name, email, day_of_week, hour, minute, timezone, enabled, created_at, updated_at)
                VALUES (:id, :project_id, :name, :email, :day_of_week, :hour, :minute, :timezone, 1, :now, :now)
            """,
            values={
                "id": schedule_id,
                "project_id": context.project_id,
                "name": body.name,
                "email": body.email,
                "day_of_week": body.day_of_week,
                "hour": body.hour,
                "minute": body.minute,
                "timezone": body.timezone,
                "now": now,
            }
        )

        # Scheduler'a ekle
        report_scheduler.add_schedule_job(schedule_id, body.day_of_week, body.hour, body.minute, body.timezone)

        return ReportScheduleResponse(
            id=schedule_id,
            project_id=context.project_id,
            name=body.name,
            email=body.email,
            day_of_week=body.day_of_week,
            hour=body.hour,
            minute=body.minute,
            timezone=body.timezone,
            enabled=True,
            created_at=now.isoformat(),
        )

    except HTTPException:
        raise
    except Exception as e:
        LOG.error(f"Error creating schedule: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get(
    "/reports/schedules",
    description="List report schedules",
    status_code=status.HTTP_200_OK,
)
async def list_schedules(
    request: Request,
    X_Auth_Token: str = Header(default=None),
):
    try:
        context = await utils.req_context_from_scope(request.scope)
        policy.authorize(context, 'metric:get', {"project_id": context.project_id})

        from safir_monitoring.db.base import DB, inject_db
        await inject_db()
        db = DB.get()

        rows = await db.fetch_all(
            query="""
                SELECT * FROM report_schedules
                WHERE project_id = :project_id AND deleted_at IS NULL
                ORDER BY created_at DESC
            """,
            values={"project_id": context.project_id}
        )

        schedules = []
        for row in rows:
            r = dict(row._mapping)
            schedules.append(ReportScheduleResponse(
                id=r["id"],
                project_id=r["project_id"],
                name=r["name"],
                email=r["email"],
                day_of_week=r["day_of_week"],
                hour=r["hour"],
                minute=r["minute"],
                timezone=r.get("timezone", "Europe/Istanbul"),
                enabled=r["enabled"],
                last_run=r["last_run"].isoformat() if r.get("last_run") else None,
                created_at=r["created_at"].isoformat() if r.get("created_at") else None,
            ))

        return {"schedules": schedules, "total": len(schedules)}

    except HTTPException:
        raise
    except Exception as e:
        LOG.error(f"Error listing schedules: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.put(
    "/reports/schedules/{schedule_id}",
    description="Update a report schedule",
    response_model=ReportScheduleResponse,
)
async def update_schedule(
    request: Request,
    schedule_id: str,
    body: ReportScheduleUpdate,
    X_Auth_Token: str = Header(default=None),
):
    try:
        context = await utils.req_context_from_scope(request.scope)
        policy.authorize(context, 'metric:get', {"project_id": context.project_id})

        from safir_monitoring.db.base import DB, inject_db
        await inject_db()
        db = DB.get()

        # Mevcut kaydi al
        row = await db.fetch_one(
            query="SELECT * FROM report_schedules WHERE id = :id AND project_id = :pid AND deleted_at IS NULL",
            values={"id": schedule_id, "pid": context.project_id}
        )
        if not row:
            raise HTTPException(status_code=404, detail="Schedule not found")

        current = dict(row._mapping)

        # Guncelle
        updates = {}
        if body.name is not None:
            updates["name"] = body.name
        if body.email is not None:
            updates["email"] = body.email
        if body.day_of_week is not None:
            if body.day_of_week not in VALID_DAYS:
                raise HTTPException(status_code=400, detail=f"Invalid day_of_week: {body.day_of_week}")
            updates["day_of_week"] = body.day_of_week
        if body.hour is not None:
            updates["hour"] = body.hour
        if body.minute is not None:
            updates["minute"] = body.minute
        if body.timezone is not None:
            updates["timezone"] = body.timezone
        if body.enabled is not None:
            updates["enabled"] = body.enabled

        if not updates:
            raise HTTPException(status_code=400, detail="No fields to update")

        updates["updated_at"] = datetime.now()
        set_clause = ", ".join(f"{k} = :{k}" for k in updates)
        updates["id"] = schedule_id

        await db.execute(
            query=f"UPDATE report_schedules SET {set_clause} WHERE id = :id",
            values=updates
        )

        # Scheduler guncelle
        new_day = updates.get("day_of_week", current["day_of_week"])
        new_hour = updates.get("hour", current["hour"])
        new_minute = updates.get("minute", current["minute"])
        new_tz = updates.get("timezone", current.get("timezone", "Europe/Istanbul"))
        new_enabled = updates.get("enabled", current["enabled"])

        if new_enabled:
            report_scheduler.add_schedule_job(schedule_id, new_day, new_hour, new_minute, new_tz)
        else:
            report_scheduler.remove_schedule_job(schedule_id)

        return ReportScheduleResponse(
            id=schedule_id,
            project_id=context.project_id,
            name=updates.get("name", current["name"]),
            email=updates.get("email", current["email"]),
            day_of_week=new_day,
            hour=new_hour,
            minute=new_minute,
            timezone=new_tz,
            enabled=new_enabled,
            last_run=current["last_run"].isoformat() if current.get("last_run") else None,
            created_at=current["created_at"].isoformat() if current.get("created_at") else None,
        )

    except HTTPException:
        raise
    except Exception as e:
        LOG.error(f"Error updating schedule: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.delete(
    "/reports/schedules/{schedule_id}",
    description="Delete a report schedule",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_schedule(
    request: Request,
    schedule_id: str,
    X_Auth_Token: str = Header(default=None),
):
    try:
        context = await utils.req_context_from_scope(request.scope)
        policy.authorize(context, 'metric:get', {"project_id": context.project_id})

        from safir_monitoring.db.base import DB, inject_db
        await inject_db()
        db = DB.get()

        result = await db.execute(
            query="UPDATE report_schedules SET deleted_at = :now WHERE id = :id AND project_id = :pid AND deleted_at IS NULL",
            values={"now": datetime.now(), "id": schedule_id, "pid": context.project_id}
        )

        report_scheduler.remove_schedule_job(schedule_id)

    except HTTPException:
        raise
    except Exception as e:
        LOG.error(f"Error deleting schedule: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post(
    "/reports/send-now",
    description="Send a report immediately (for testing)",
    status_code=status.HTTP_200_OK,
)
async def send_report_now(
    request: Request,
    email: str = Query(..., description="Alici email adresi"),
    X_Auth_Token: str = Header(default=None),
):
    try:
        context = await utils.req_context_from_scope(request.scope)
        policy.authorize(context, 'metric:get', {"project_id": context.project_id})

        from safir_monitoring.db.base import DB, inject_db
        from safir_monitoring.reporting import report_generator, email_sender
        from jinja2 import Template
        from pathlib import Path
        from datetime import timedelta

        await inject_db()
        db = DB.get()

        host_summary = await report_generator.get_host_metrics_summary(db)
        placement_summary = await report_generator.get_placement_summary(db)
        rightsizing = await report_generator.get_rightsizing_summary(db)
        trend_data = await report_generator.get_weekly_trend_data(db)
        charts = report_generator.generate_trend_charts(trend_data)

        excel_bytes = report_generator.generate_excel(
            host_summary, placement_summary, rightsizing, trend_data
        )

        end_date = datetime.now()
        start_date = end_date - timedelta(days=7)
        # Template yolu: hem pip install hem de development modunda calisir
        import safir_monitoring.reporting
        template_path = Path(safir_monitoring.reporting.__file__).parent / "templates" / "weekly_report.html"
        template = Template(template_path.read_text(encoding="utf-8"))
        html_body = template.render(
            start_date=start_date.strftime("%d/%m/%Y"),
            end_date=end_date.strftime("%d/%m/%Y"),
            host_summary=host_summary,
            placement_summary=placement_summary,
            rightsizing=rightsizing,
            charts=charts,
        )

        subject = f"Safir Bulut Haftalik Rapor - {end_date.strftime('%d/%m/%Y')}"
        filename = f"safir_weekly_report_{end_date.strftime('%Y%m%d')}.xlsx"
        success = email_sender.send_report_email(email, subject, html_body, excel_bytes, filename)

        return {"status": "sent" if success else "failed", "email": email}

    except HTTPException:
        raise
    except Exception as e:
        LOG.error(f"Error sending report: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
