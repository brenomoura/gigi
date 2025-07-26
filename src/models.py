from typing import TypedDict

import msgspec


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
