from datetime import datetime, timedelta, timezone

import msgspec
from starlette.responses import JSONResponse, Response
from starlette.routing import Route

from src import globals
from src.db import get_summary
from src.encoders import encoder, payment_decoder


async def get_payments_summary(from_date: datetime, to_date: datetime):
    return await get_summary(from_date, to_date)


async def payments(request):
    try:
        payment_body = await request.body()
        payment = payment_decoder.decode(payment_body)
        await globals.payment_queue.put(payment)
    except msgspec.ValidationError as e:
        return JSONResponse({"error": str(e)}, status_code=400)
    return JSONResponse({"msg": "payment created"}, status_code=201)


async def payments_summary(request):
    try:
        now = datetime.now(timezone.utc)
        from_str = request.query_params.get("from")
        to_str = request.query_params.get("to")
        from_date = (
            datetime.fromisoformat(from_str) if from_str else now - timedelta(days=30)
        )
        to_date = datetime.fromisoformat(to_str) if to_str else now
        summary = await get_payments_summary(from_date, to_date)
    except msgspec.ValidationError as e:
        return JSONResponse({"error": str(e)}, status_code=400)
    return Response(content=encoder.encode(summary), media_type="application/json")


async def purge_payments(request):
    try:
        last_health_check = await globals.redis_client.get("payment_processor_health") # gamb
        await globals.redis_client.flushdb()
        await globals.redis_client.set("payment_processor_health", last_health_check) # iarra
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)
    return JSONResponse({"msg": "payments purged"}, status_code=200)


routes = [
    Route("/payments", payments, methods=["POST"]),
    Route("/payments-summary", payments_summary, methods=["GET"]),
    Route("/purge-payments", purge_payments, methods=["POST"]),
]
