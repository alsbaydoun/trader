from app.brokers.base import Broker
from app.domain.models import OrderRequest, Position


class MT5Broker(Broker):
    """Integration seam for MetaTrader 5 / JustMarkets.

    The real adapter should run on the Windows host where MT5 is installed, validate symbol names
    against the broker terminal, and never bypass the API risk engine.
    """

    def __init__(self, live_unlocked: bool) -> None:
        self.live_unlocked = live_unlocked

    def positions(self) -> list[Position]:
        return []

    def place_order(self, order: OrderRequest) -> Position:
        if not self.live_unlocked:
            raise PermissionError("MT5 live trading is locked by configuration.")
        raise NotImplementedError(
            "Install MetaTrader5 and implement account-specific order mapping."
        )
