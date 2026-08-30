from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from typing import Literal


class Direction(str, Enum):
    buy = "buy"
    sell = "sell"
    hold = "hold"


class TradeMode(str, Enum):
    signal_only = "signal_only"
    auto_trade = "auto_trade"


@dataclass(frozen=True)
class Candle:
    symbol: str
    timeframe: str
    ts: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float
    source: Literal["demo", "mt5"] = "demo"


@dataclass(frozen=True)
class SignalReason:
    category: str
    message: str
    impact: Literal["bullish", "bearish", "neutral", "risk"]
    weight: float


@dataclass(frozen=True)
class Signal:
    symbol: str
    timeframe: str
    direction: Direction
    confidence: float
    entry: float
    stop_loss: float | None
    take_profit: float | None
    reasons: list[SignalReason]
    source: Literal["demo", "mt5"] = "demo"
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))


@dataclass(frozen=True)
class OrderRequest:
    symbol: str
    direction: Direction
    volume: float
    entry: float
    stop_loss: float | None
    take_profit: float | None
    mode: TradeMode


@dataclass(frozen=True)
class RiskDecision:
    approved: bool
    reason: str
    max_volume: float


@dataclass(frozen=True)
class Position:
    id: str
    symbol: str
    direction: Direction
    volume: float
    entry: float
    stop_loss: float | None
    take_profit: float | None
    opened_at: datetime
