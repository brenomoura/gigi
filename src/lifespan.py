import asyncio
import contextlib

from src import globals
from src.worker import payment_worker, retry_payment_worker, payment_processor_health_checker


@contextlib.asynccontextmanager
async def lifespan(app):
    globals.init_globals()
    health_checker_task = asyncio.create_task(payment_processor_health_checker())
    num_workers = globals.num_workers
    payment_tasks = [asyncio.create_task(payment_worker()) for _ in range(num_workers)]
    retry_payment_tasks = [
        asyncio.create_task(retry_payment_worker()) for _ in range(num_workers)
    ]
    yield
    for _ in payment_tasks:
        await globals.payment_queue.put(None)
    for _ in retry_payment_tasks:
        await globals.retry_payment_queue.put(None)
    await asyncio.gather(*payment_tasks)
    await asyncio.gather(*retry_payment_tasks)
    try:
        health_checker_task.cancel()
    except asyncio.CancelledError:
        pass
    if globals.session:
        await globals.session.close()
