import asyncio

from arq import cron

from app.ai.embeddings import load_model as load_embedding_model
from app.config import settings
from app.tasks.email_tasks import send_email_task
from app.tasks.health_check_tasks import check_google_calendar_health
from app.tasks.queue import get_redis_settings
from app.tasks.reminder_tasks import send_appointment_reminders
from app.tasks.retention_tasks import prune_old_conversations
from app.tasks.whatsapp_tasks import (
    process_whatsapp_message,
    process_whatsapp_status_update,
    process_whatsapp_voice_message,
    send_unsupported_message_reply,
)


async def startup(ctx: dict) -> None:
    # The arq worker is a separate OS process from uvicorn and never runs
    # main.py's lifespan, so anything that must be initialized at startup
    # (embedding model, Sentry) must be done here too.

    # Sentry — mirrors main.py's init but uses only integrations that make
    # sense in a worker process.  FastApiIntegration / StarletteIntegration
    # are HTTP-layer hooks and are intentionally omitted here.  AsyncioIntegration
    # patches asyncio's exception handling so unhandled coroutine exceptions
    # (including a re-raised EmailDeliveryError from send_email_task, or any
    # uncaught exception in process_whatsapp_message, process_whatsapp_voice_message,
    # etc.) are captured as Sentry issues rather than silently dying in the
    # worker's event loop.
    if settings.SENTRY_DSN:
        import sentry_sdk
        from sentry_sdk.integrations.asyncio import AsyncioIntegration
        from sentry_sdk.integrations.sqlalchemy import SqlalchemyIntegration

        sentry_sdk.init(
            dsn=settings.SENTRY_DSN,
            environment=settings.APP_ENV,
            traces_sample_rate=settings.SENTRY_TRACES_SAMPLE_RATE,
            send_default_pii=False,
            integrations=[
                SqlalchemyIntegration(),
                AsyncioIntegration(),
            ],
        )

    await asyncio.to_thread(load_embedding_model)


class WorkerSettings:
    # Tuned for remote Redis — see get_redis_settings() for why the arq
    # default 1s timeout crashes the worker on a transient network blip.
    redis_settings = get_redis_settings()
    on_startup = startup
    # On-demand jobs, enqueued via app.tasks.queue.get_arq_pool().enqueue_job(...)
    functions = [send_email_task, process_whatsapp_message, process_whatsapp_status_update, process_whatsapp_voice_message, send_unsupported_message_reply]
    cron_jobs = [
        cron(send_appointment_reminders, minute={0, 15, 30, 45}),
        cron(check_google_calendar_health, minute=5),  # hourly, at :05
        cron(prune_old_conversations, hour=2, minute=0),  # nightly at 02:00 UTC
    ]
