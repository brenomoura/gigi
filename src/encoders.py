from datetime import datetime

import msgspec

from src.models import PaymentRequest, HealthCheck

encoder = msgspec.json.Encoder()
health_check_decoder = msgspec.json.Decoder(HealthCheck)
payment_decoder = msgspec.json.Decoder(PaymentRequest)
datetime_decoder = msgspec.json.Decoder(datetime)
