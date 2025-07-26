from datetime import datetime

import msgspec

from src.models import PaymentRequest

encoder = msgspec.json.Encoder()
payment_decoder = msgspec.json.Decoder(PaymentRequest)
datetime_decoder = msgspec.json.Decoder(datetime)
