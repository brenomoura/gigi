import asyncio
import contextlib

from src.db import purge_payments
from src import globals
from src.worker import (
    payment_processor_health_checker,
    payment_worker,
)


@contextlib.asynccontextmanager
async def lifespan(app):
    globals.init_globals()
    await purge_payments()
    health_checker_task = asyncio.create_task(payment_processor_health_checker())
    num_workers = globals.num_workers
    payment_tasks = [asyncio.create_task(payment_worker()) for _ in range(num_workers)]
    yield
    for _ in payment_tasks:
        await globals.payment_queue.put(None)
    await asyncio.gather(*payment_tasks)
    try:
        health_checker_task.cancel()
    except asyncio.CancelledError:
        pass
    if globals.session:
        await globals.session.close()
