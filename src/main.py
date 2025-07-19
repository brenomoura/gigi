import asyncio
import contextlib
import logging
import os
import sqlite3
from datetime import datetime, timedelta, timezone
from typing import TypedDict

import aiohttp
import msgspec
from dotenv import load_dotenv
from starlette.applications import Starlette
from starlette.responses import JSONResponse, Response
from starlette.routing import Route

logging.basicConfig(
    level=logging.INFO,  # Ou DEBUG, WARNING, ERROR
    format="%(asctime)s - %(levelname)s - %(message)s",
)

load_dotenv()
payment_processor_url = os.getenv("PAYMENT_PROCESSOR_URL")
fallback_payment_processor_url = os.getenv("FALLBACK_PAYMENT_PROCESSOR_URL")
database_url = os.getenv("DATABASE_URL")
if not payment_processor_url or not fallback_payment_processor_url:
    raise ValueError(
        "PAYMENT_PROCESSOR_URL and FALLBACK_PAYMENT_PROCESSOR_URL must be set in the environment variables."
    )


class BaseSummary(msgspec.Struct):
    total_requests: int = msgspec.field(name="totalRequests")
    total_amount: float = msgspec.field(name="totalAmount")


class PaymentsSummaryResponse(msgspec.Struct):
    default: BaseSummary
    fallback: BaseSummary


class PaymentRequest(TypedDict):
    correlationId: str
    amount: float


class Payment(TypedDict):
    id: int
    correlation_id: str
    amount: float
    requested_at: str  # ISO 8601 format
    payment_processor: str = "default"  # or "fallback"


encoder = msgspec.json.Encoder()
paymentDecoder = msgspec.json.Decoder(PaymentRequest)
datetimeDecoder = msgspec.json.Decoder(datetime)

payment_queue = asyncio.Queue()
workers = []


def get_db_conn():
    return sqlite3.connect(database_url, check_same_thread=False)


def initialize_db():
    db_path = database_url
    if os.path.exists(db_path):
        os.remove(db_path)  # just remove to ensure a fresh start
    conn = get_db_conn()
    cursor = conn.cursor()
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS payments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            correlation_id TEXT NOT NULL,
            amount REAL NOT NULL,
            payment_processor TEXT NOT NULL,
            requested_at TEXT NOT NULL
        )
        """
    )
    conn.commit()
    conn.close()


def register_payment_db(payment):
    conn = get_db_conn()
    cursor = conn.cursor()
    cursor.execute(
        """
        INSERT INTO payments (correlation_id, amount, payment_processor, requested_at)
        VALUES (?, ?, ?, ?)
        """,
        (
            payment["correlation_id"],
            payment["amount"],
            payment["payment_processor"],
            payment["requested_at"],
        ),
    )
    conn.commit()
    conn.close()
    logging.info(
        f"Payment registered: {payment['correlation_id']} - {payment['amount']} using {payment['payment_processor']}"
    )


def get_payments_summary(
    from_date: datetime, to_date: datetime
) -> PaymentsSummaryResponse:
    conn = get_db_conn()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT COUNT(*), COALESCE(SUM(amount), 0) FROM payments WHERE payment_processor = 'default' AND requested_at BETWEEN ? AND ?",
        (from_date.isoformat(), to_date.isoformat()),
    )
    default_summary = cursor.fetchone() or (0, 0.0)

    cursor.execute(
        "SELECT COUNT(*), COALESCE(SUM(amount), 0) FROM payments WHERE payment_processor = 'fallback' AND requested_at BETWEEN ? AND ?",
        (from_date.isoformat(), to_date.isoformat()),
    )
    fallback_summary = cursor.fetchone() or (0, 0.0)

    conn.close()

    return PaymentsSummaryResponse(
        default=BaseSummary(
            total_requests=default_summary[0], total_amount=default_summary[1]
        ),
        fallback=BaseSummary(
            total_requests=fallback_summary[0], total_amount=fallback_summary[1]
        ),
    )


async def make_payment_request(payment_payload, max_attempts=10) -> str:
    urls = [
        (f"{payment_processor_url}/payments", "default"),
        (f"{fallback_payment_processor_url}/payments", "fallback"),
    ]
    attempt = 0
    async with aiohttp.ClientSession() as session:
        while attempt < max_attempts:
            url, processor = urls[attempt % 2]
            logging.info(f"Attempt {attempt + 1}: Sending payment request to {url}")
            async with session.post(url, json=payment_payload) as response:
                if response.status == 200:
                    logging.info(f"Payment request successful: {await response.json()}")
                    return processor
                attempt += 1
    raise Exception("Both payment processors failed after multiple attempts.")


async def payment_worker():
    while True:
        payment_request = await payment_queue.get()
        if payment_request is None:
            break
        requested_at = datetime.now(timezone.utc)
        payment_request["requestedAt"] = requested_at.isoformat()
        try:
            processor = await make_payment_request(payment_request)
            payment = Payment(
                id=None,  # ID will be auto-generated by the database
                correlation_id=payment_request["correlationId"],
                amount=payment_request["amount"],
                requested_at=requested_at.isoformat(),
                payment_processor=processor,
            )
            register_payment_db(payment)
        except Exception as e:
            logging.error(f"Error processing payment request: {e}")

        payment_queue.task_done()


@contextlib.asynccontextmanager
async def lifespan(app):
    initialize_db()
    num_workers = 4
    tasks = [asyncio.create_task(payment_worker()) for _ in range(num_workers)]
    app.state.worker_tasks = tasks
    yield
    for _ in tasks:
        await payment_queue.put(None)
    await asyncio.gather(*tasks)


async def payments(request):
    try:
        paymentBody = await request.body()
        payment = paymentDecoder.decode(paymentBody)
        await payment_queue.put(payment)
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
        summary = get_payments_summary(from_date, to_date)
    except msgspec.ValidationError as e:
        return JSONResponse({"error": str(e)}, status_code=400)
    return Response(content=encoder.encode(summary), media_type="application/json")


app = Starlette(
    debug=True,
    routes=[
        Route("/payments", payments, methods=["POST"]),
        Route("/payments-summary", payments_summary, methods=["GET"]),
    ],
    lifespan=lifespan,
)
