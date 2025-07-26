import asyncio
import contextlib

from src import globals
from src.db import purge_payments
from src.workers import (
    payment_worker,
)


@contextlib.asynccontextmanager
async def lifespan(app):
    globals.init_globals()
    await purge_payments()
    num_workers = globals.num_workers
    payment_tasks = [asyncio.create_task(payment_worker()) for _ in range(num_workers)]
    yield
    for _ in payment_tasks:
        await globals.payment_queue.put(None)
    await asyncio.gather(*payment_tasks)
    if globals.session:
        await globals.session.close()
