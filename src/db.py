from datetime import datetime

import msgspec

from src import globals
from src.encoders import encoder
from src.models import BaseSummary, Payment, PaymentsSummaryResponse
from src.utils import from_cents, to_cents


async def register_payment_db(payment: Payment):
    payment["amount"] = to_cents(payment["amount"])
    value = encoder.encode(payment)
    timestamp = datetime.fromisoformat(payment["requested_at"]).timestamp()

    async with globals.redis_client.pipeline() as pipe:
        await pipe.zadd(f"payments_index:{payment['payment_processor']}", {value: timestamp})
        await pipe.execute()


async def get_summary(from_date: datetime, to_date: datetime):
    from_ts = from_date.timestamp()
    to_ts = to_date.timestamp()

    async def get_summary_for(processor):
        payment_scores = await globals.redis_client.zrangebyscore(
            f"payments_index:{processor}", from_ts, to_ts, withscores=True
        )

        total_amount = 0
        count = len(payment_scores)

        for payment_data, _ in payment_scores:
            try:
                payment = msgspec.json.decode(payment_data)
                total_amount += payment["amount"]
            except Exception:
                count -= 1
                continue

        return BaseSummary(total_requests=count, total_amount=total_amount)

    default_summary = await get_summary_for("default")
    default_summary.total_amount = from_cents(default_summary.total_amount)
    fallback_summary = await get_summary_for("fallback")
    fallback_summary.total_amount = from_cents(fallback_summary.total_amount)
    return PaymentsSummaryResponse(
        default=default_summary,
        fallback=fallback_summary,
    )


async def purge_payments():
    await globals.redis_client.flushdb()
    globals.logger.info("Payments database purged.")
