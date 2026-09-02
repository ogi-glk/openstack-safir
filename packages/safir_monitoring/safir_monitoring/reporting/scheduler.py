"""APScheduler entegrasyonu — rapor zamanlamalarini yonetir.

FastAPI on_startup'ta baslatilir, DB'deki aktif zamanlamalari yukler.
API uzerinden zamanlama eklendiginde/silindiginde scheduler guncellenir.
"""

import asyncio
from datetime import datetime
from pathlib import Path

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from jinja2 import Template
from oslo_log import log as logging

LOG = logging.getLogger(__name__)

_scheduler = None

TEMPLATE_PATH = Path(__file__).parent / "templates" / "weekly_report.html"


def get_scheduler():
    global _scheduler
    if _scheduler is None:
        _scheduler = AsyncIOScheduler()
    return _scheduler


async def send_scheduled_report(schedule_id: str):
    """Zamanlanmis raporu olusturur ve gonderir."""
    from safir_monitoring.db.base import DB, inject_db
    from safir_monitoring.reporting import report_generator, email_sender

    LOG.info(f"Running scheduled report: {schedule_id}")

    try:
        await inject_db()
        db = DB.get()

        # Zamanlama bilgisini al
        row = await db.fetch_one(
            query="SELECT * FROM report_schedules WHERE id = :id AND deleted_at IS NULL",
            values={"id": schedule_id}
        )
        if not row:
            LOG.warning(f"Schedule {schedule_id} not found or deleted")
            return

        schedule = dict(row._mapping)
        email_addr = schedule["email"]
        name = schedule["name"]

        # Verileri topla
        host_summary = await report_generator.get_host_metrics_summary(db)
        placement_summary = await report_generator.get_placement_summary(db)
        rightsizing = await report_generator.get_rightsizing_summary(db)
        trend_data = await report_generator.get_weekly_trend_data(db)
        charts = report_generator.generate_trend_charts(trend_data)

        # Excel olustur
        excel_bytes = report_generator.generate_excel(
            host_summary, placement_summary, rightsizing, trend_data
        )

        # HTML render
        end_date = datetime.now()
        start_date = end_date - __import__('datetime').timedelta(days=7)
        template_text = TEMPLATE_PATH.read_text(encoding="utf-8")
        template = Template(template_text)
        html_body = template.render(
            start_date=start_date.strftime("%d/%m/%Y"),
            end_date=end_date.strftime("%d/%m/%Y"),
            host_summary=host_summary,
            placement_summary=placement_summary,
            rightsizing=rightsizing,
            charts=charts,
        )

        # Mail gonder
        subject = f"Safir Bulut Haftalik Rapor - {name} - {end_date.strftime('%d/%m/%Y')}"
        filename = f"safir_weekly_report_{end_date.strftime('%Y%m%d')}.xlsx"
        success = email_sender.send_report_email(
            to_addr=email_addr,
            subject=subject,
            html_body=html_body,
            excel_bytes=excel_bytes,
            excel_filename=filename,
        )

        # last_run guncelle
        if success:
            await db.execute(
                query="UPDATE report_schedules SET last_run = :now WHERE id = :id",
                values={"now": datetime.now(), "id": schedule_id}
            )

        LOG.info(f"Report {'sent' if success else 'FAILED'} to {email_addr}")

    except Exception as e:
        LOG.error(f"Failed to send scheduled report {schedule_id}: {e}", exc_info=True)


def add_schedule_job(schedule_id: str, day_of_week: str, hour: int, minute: int, timezone: str = "Europe/Istanbul"):
    """Scheduler'a yeni bir rapor job'i ekler."""
    scheduler = get_scheduler()
    job_id = f"report_{schedule_id}"

    # Varsa kaldir
    if scheduler.get_job(job_id):
        scheduler.remove_job(job_id)

    scheduler.add_job(
        send_scheduled_report,
        CronTrigger(day_of_week=day_of_week, hour=hour, minute=minute, timezone=timezone),
        args=[schedule_id],
        id=job_id,
        replace_existing=True,
    )
    LOG.info(f"Scheduled report job: {job_id} -> {day_of_week} {hour:02d}:{minute:02d} ({timezone})")


def remove_schedule_job(schedule_id: str):
    """Scheduler'dan rapor job'ini kaldirir."""
    scheduler = get_scheduler()
    job_id = f"report_{schedule_id}"
    if scheduler.get_job(job_id):
        scheduler.remove_job(job_id)
        LOG.info(f"Removed report job: {job_id}")


async def load_schedules_from_db():
    """DB'deki aktif zamanlamalari scheduler'a yukler."""
    from safir_monitoring.db.base import DB, inject_db

    try:
        await inject_db()
        db = DB.get()
        rows = await db.fetch_all(
            query="SELECT * FROM report_schedules WHERE enabled = 1 AND deleted_at IS NULL"
        )
        for row in rows:
            s = dict(row._mapping)
            add_schedule_job(s["id"], s["day_of_week"], s["hour"], s["minute"], s.get("timezone", "Europe/Istanbul"))
        LOG.info(f"Loaded {len(rows)} report schedules from DB")
    except Exception as e:
        LOG.warning(f"Failed to load report schedules: {e}")
