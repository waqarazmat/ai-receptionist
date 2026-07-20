import asyncio

from arq import cron

from app.ai.embeddings import load_model as load_embedding_model
from app.tasks.health_check_tasks import check_google_calendar_health
from app.tasks.queue import get_redis_settings
from app.tasks.reminder_tasks import send_appointment_reminders
from app.tasks.whatsapp_tasks import (
    process_whatsapp_message,
    process_whatsapp_status_update,
    send_unsupported_message_reply,
)


async def startup(ctx: dict) -> None:
    # The arq worker is a separate OS process from uvicorn and never runs
    # main.py's lifespan, so the embedding model has to be loaded here too —
    # otherwise any task touching embed_text() (RAG/FAQ handling) crashes
    # with "Embedding model not loaded".
    await asyncio.to_thread(load_embedding_model)


class WorkerSettings:
    # Tuned for remote Redis — see get_redis_settings() for why the arq
    # default 1s timeout crashes the worker on a transient network blip.
    redis_settings = get_redis_settings()
    on_startup = startup
    # On-demand jobs, enqueued via app.tasks.queue.get_arq_pool().enqueue_job(...)
    functions = [process_whatsapp_message, process_whatsapp_status_update, send_unsupported_message_reply]
    cron_jobs = [
        cron(send_appointment_reminders, minute={0, 15, 30, 45}),
        cron(check_google_calendar_health, minute=5),  # hourly, at :05
    ]
