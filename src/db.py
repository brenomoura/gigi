from datetime import datetime

from src import globals
from src.encoders import encoder
from src.models import Payment


async def register_payment_db(payment: Payment):
    key = f"payment:{payment['correlation_id']}"
    value = encoder.encode(payment)
    async with globals.redis_client.pipeline() as pipe:
        await pipe.set(key, value)
        await pipe.zadd(
            "payments_index",
            {
                payment["requested_at"]: datetime.fromisoformat(
                    payment["requested_at"]
                ).timestamp()
            },
        )
        await pipe.rpush(f"payments:{payment['payment_processor']}", value)
        await pipe.execute()
    globals.logger.info(
        f"Payment registered: {payment['correlation_id']} - {payment['amount']} using {payment['payment_processor']}"
    )
