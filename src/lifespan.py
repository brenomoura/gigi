import asyncio
import contextlib

from src import globals
from src.worker import payment_worker


@contextlib.asynccontextmanager
async def lifespan(app):
    globals.init_globals()
    num_workers = globals.num_workers
    tasks = [asyncio.create_task(payment_worker()) for _ in range(num_workers)]
    app.state.worker_tasks = tasks
    yield
    for _ in tasks:
        await globals.payment_queue.put(None)
    await asyncio.gather(*tasks)
    if globals.session:
        await globals.session.close()
