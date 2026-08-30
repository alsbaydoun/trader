from datetime import UTC, datetime
from uuid import uuid4

from app.brokers.base import Broker
from app.domain.models import OrderRequest, Position


class PaperBroker(Broker):
    def __init__(self) -> None:
        self._positions: list[Position] = []

    def positions(self) -> list[Position]:
        return list(self._positions)

    def place_order(self, order: OrderRequest) -> Position:
        position = Position(
            id=f"paper-{uuid4().hex[:12]}",
            symbol=order.symbol,
            direction=order.direction,
            volume=order.volume,
            entry=order.entry,
            stop_loss=order.stop_loss,
            take_profit=order.take_profit,
            opened_at=datetime.now(UTC),
        )
        self._positions.append(position)
        return position
