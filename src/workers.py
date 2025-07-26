import asyncio
import time
from datetime import datetime, timezone

import aiohttp

from src import globals
from src.db import register_payment_db
from src.models import Payment


async def make_payment_request(payment_payload, processor, max_attempts=3) -> str:
    urls = {
        "default": globals.payment_processor_url + "/payments",
        "fallback": globals.fallback_payment_processor_url + "/payments",
    }
    timeout_value = 1.0 if processor == "default" else 10.0
    timeout = aiohttp.ClientTimeout(total=timeout_value)

    start_time = time.perf_counter()
    correlation_id = payment_payload.get("correlationId", "unknown")

    for attempt in range(max_attempts):
        attempt_start = time.perf_counter()

        async with globals.payment_processor_semaphore:
            try:
                async with globals.session.post(
                    urls[processor], json=payment_payload, timeout=timeout
                ) as response:
                    attempt_duration = time.perf_counter() - attempt_start

                    if response.status == 200:
                        total_duration = time.perf_counter() - start_time
                        globals.logger.debug(
                            f"Payment {correlation_id}: SUCCESS {processor} attempt {attempt + 1}/{max_attempts} in {attempt_duration:.3f}s (total: {total_duration:.3f}s)"
                        )
                        return processor
                    else:
                        globals.logger.warning(
                            f"Payment {correlation_id}: {processor} returned status {response.status} in {attempt_duration:.3f}s (attempt {attempt + 1}/{max_attempts})"
                        )

            except Exception as e:
                attempt_duration = time.perf_counter() - attempt_start
                globals.logger.warning(
                    f"Payment {correlation_id}: {processor} failed attempt {attempt + 1}/{max_attempts} in {attempt_duration:.3f}s: {type(e).__name__}"
                )

                if attempt == max_attempts - 1:
                    break
                await asyncio.sleep(0.1)

    total_duration = time.perf_counter() - start_time

    if processor == "default":
        globals.logger.info(
            f"Payment {correlation_id}: Default failed after {max_attempts} attempts in {total_duration:.3f}s, trying fallback"
        )
        return await make_payment_request(payment_payload, "fallback", 1)

    globals.logger.error(
        f"Payment {correlation_id}: Both processors failed in {total_duration:.3f}s"
    )
    raise Exception("Both payment processors failed")


async def payment_worker():
    while True:
        await process_from_queue()


async def process_from_queue():
    payment_request = await globals.payment_queue.get()

    if payment_request is None:
        return

    await process_payment(payment_request)
    globals.payment_queue.task_done()


async def process_payment(payment_request):
    requested_at = datetime.now(timezone.utc)
    try:
        payment_request["requestedAt"] = requested_at.isoformat()
        payment_processor = await make_payment_request(
            payment_request, processor="default"
        )

        payment = Payment(
            id=None,
            correlation_id=payment_request["correlationId"],
            amount=payment_request["amount"],
            requested_at=requested_at.isoformat(),
            payment_processor=payment_processor,
        )
        await register_payment_db(payment)

    except Exception:
        await globals.payment_queue.put(payment_request)
