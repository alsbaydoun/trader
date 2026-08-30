from prometheus_client import Counter, Gauge, generate_latest
from prometheus_client.openmetrics.exposition import CONTENT_TYPE_LATEST
from starlette.responses import Response

SIGNALS_GENERATED = Counter("trader_signals_generated_total", "Signals generated", ["symbol"])
ORDERS_REJECTED = Counter(
    "trader_orders_rejected_total",
    "Orders rejected by guardrails",
    ["reason"],
)
OPEN_POSITIONS = Gauge("trader_open_positions", "Open positions tracked by the broker facade")
MT5_CONNECTED = Gauge("trader_mt5_connected", "Whether the local MT5 terminal is connected")
MT5_ACCOUNT_MATCH = Gauge(
    "trader_mt5_account_match",
    "Whether the MT5 terminal account matches the selected workstation account",
)


def metrics_response() -> Response:
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)
