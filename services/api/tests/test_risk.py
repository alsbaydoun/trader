from datetime import UTC, datetime

from app.domain.models import Direction, OrderRequest, Position, TradeMode
from app.services.risk import RiskEngine


def make_engine() -> RiskEngine:
    return RiskEngine(
        account_equity=10000,
        max_risk_per_trade_pct=0.5,
        max_daily_loss_pct=2,
        max_open_positions=2,
        max_symbol_exposure_pct=5,
    )


def test_rejects_order_without_stop_loss() -> None:
    order = OrderRequest("XAUUSD", Direction.buy, 0.01, 2340, None, 2350, TradeMode.auto_trade)

    decision = make_engine().evaluate(order, [])

    assert not decision.approved
    assert "stop loss" in decision.reason.lower()


def test_rejects_when_open_position_limit_reached() -> None:
    positions = [
        Position("1", "XAUUSD", Direction.buy, 0.01, 2340, 2330, 2360, datetime.now(UTC)),
        Position("2", "BTCUSD", Direction.sell, 0.01, 64000, 65000, 62000, datetime.now(UTC)),
    ]
    order = OrderRequest("WTI.m", Direction.buy, 0.01, 78, 77, 80, TradeMode.auto_trade)

    decision = make_engine().evaluate(order, positions)

    assert not decision.approved
    assert "open positions" in decision.reason.lower()


def test_approves_small_guarded_order() -> None:
    order = OrderRequest("WTI.m", Direction.buy, 0.01, 78, 77, 80, TradeMode.auto_trade)

    decision = make_engine().evaluate(order, [])

    assert decision.approved
    assert decision.max_volume > 0
