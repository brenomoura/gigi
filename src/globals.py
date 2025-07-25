import asyncio
import logging
import os

import aiohttp
import redis.asyncio as redis

logging.basicConfig(
    level=logging.INFO,  # Ou DEBUG, WARNING, ERROR
    format="%(asctime)s - %(levelname)s - %(message)s",
)


def init_globals():
    global redis_client
    global session
    global health_checker_session
    global cached_health_check
    global payment_queue
    global logger
    global payment_processor_url
    global fallback_payment_processor_url
    global num_workers
    num_workers = int(os.getenv("NUM_WORKERS"))
    payment_processor_url = os.getenv("PAYMENT_PROCESSOR_URL")
    fallback_payment_processor_url = os.getenv("FALLBACK_PAYMENT_PROCESSOR_URL")
    if not payment_processor_url or not fallback_payment_processor_url:
        raise ValueError(
            "PAYMENT_PROCESSOR_URL and FALLBACK_PAYMENT_PROCESSOR_URL must be set in the environment variables."
        )

    payment_queue = asyncio.Queue()
    session = aiohttp.ClientSession()
    health_checker_session = aiohttp.ClientSession()
    cached_health_check = None
    redis_client = redis.Redis(host="redis", port=6379, decode_responses=True)
    logger = logging.getLogger("gigi")
