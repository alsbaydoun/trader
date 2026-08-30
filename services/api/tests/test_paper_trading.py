from datetime import UTC, datetime, timedelta
from pathlib import Path

from app.domain.models import Candle, Direction, SignalReason
from app.services.market_scanner import MarketOpportunity, MarketScanResult
from app.services.paper_trading import PaperTradingService


def make_service(path: Path) -> PaperTradingService:
    return PaperTradingService(
        str(path),
        enabled=True,
        starting_balance=10000,
        risk_per_trade_pct=0.1,
        max_open_positions=10,
        minimum_opportunity_score=0,
        commission_bps=1,
        slippage_bps=0,
        cycle_interval_seconds=60,
        max_position_minutes=240,
    )


def opportunity(symbol: str = "XAUUSD", direction: Direction = Direction.buy) -> MarketOpportunity:
    return MarketOpportunity(
        rank=1,
        symbol=symbol,
        description="Test market",
        category="Test",
        direction=direction,
        confidence=0.8,
        entry=100,
        stop_loss=99 if direction == Direction.buy else 101,
        take_profit=102 if direction == Direction.buy else 98,
        opportunity_score=70,
        estimated_move_pct=2,
        spread_pct=0.01,
        market_active=True,
        quote_age_seconds=1,
        recommendation="Candidate",
        reasons=[SignalReason("trend", "Trend confirmed.", "bullish", 0.4)],
    )


def scan(*items: MarketOpportunity, now: datetime) -> MarketScanResult:
    return MarketScanResult(
        source="mt5",
        timeframe="1m",
        available_symbols=len(items),
        scanned_symbols=len(items),
        generated_at=now,
        disclaimer="Virtual test",
        opportunities=list(items),
    )


def candle(*, low: float, high: float, close: float, now: datetime) -> Candle:
    return Candle("XAUUSD", "1m", now, 100, high, low, close, 1000, "mt5")


def test_opens_and_closes_target_with_detailed_result(tmp_path: Path) -> None:
    service = make_service(tmp_path / "paper.json")
    started = datetime(2026, 1, 1, tzinfo=UTC)

    opened = service.process_cycle(scan(opportunity(), now=started), {}, "test-account", started)

    assert opened.metrics.open_positions == 1
    assert opened.open_positions[0].risk_amount == 10
    assert opened.open_positions[0].reasons == ["Trend confirmed."]

    finished = service.process_cycle(
        scan(opportunity(), now=started + timedelta(minutes=1)),
        {"XAUUSD": candle(low=100, high=102.2, close=101.8, now=started)},
        "test-account",
        started + timedelta(minutes=1),
    )

    assert finished.metrics.open_positions == 0
    assert finished.metrics.closed_trades == 1
    assert finished.metrics.winning_trades == 1
    assert finished.closed_trades[0].exit_reason == "take_profit"
    assert finished.closed_trades[0].net_pnl > 0
    assert finished.decisions[0].action == "cycle"


def test_stop_is_used_when_stop_and_target_share_a_candle(tmp_path: Path) -> None:
    service = make_service(tmp_path / "paper.json")
    started = datetime(2026, 1, 1, tzinfo=UTC)
    service.process_cycle(scan(opportunity(), now=started), {}, "test-account", started)

    result = service.process_cycle(
        scan(opportunity(), now=started + timedelta(minutes=1)),
        {"XAUUSD": candle(low=98.8, high=102.2, close=100, now=started)},
        "test-account",
        started + timedelta(minutes=1),
    )

    assert result.closed_trades[0].exit_reason == "stop_loss"
    assert result.closed_trades[0].net_pnl < 0


def test_virtual_ledger_persists_without_broker_credentials(tmp_path: Path) -> None:
    path = tmp_path / "paper.json"
    service = make_service(path)
    started = datetime(2026, 1, 1, tzinfo=UTC)
    service.process_cycle(scan(opportunity(), now=started), {}, "test-account", started)

    reloaded = make_service(path).snapshot()

    assert reloaded.engine.virtual_only is True
    assert reloaded.metrics.open_positions == 1
    assert reloaded.open_positions[0].source_account_id == "test-account"
    assert "password" not in path.read_text(encoding="utf-8").lower()
    assert reloaded.persistence.status == "saved"
    assert reloaded.persistence.state_version == 2


def test_closed_outcomes_are_persisted_as_learning_feedback(tmp_path: Path) -> None:
    path = tmp_path / "paper.json"
    service = make_service(path)
    started = datetime(2026, 1, 1, tzinfo=UTC)

    service.process_cycle(scan(opportunity(), now=started), {}, "test-account", started)
    result = service.process_cycle(
        scan(opportunity(), now=started + timedelta(minutes=1)),
        {"XAUUSD": candle(low=98.8, high=102.2, close=100, now=started)},
        "test-account",
        started + timedelta(minutes=1),
    )

    assert result.learning.observations == 1
    assert result.learning.losses == 1
    assert result.learning.factor_performance[0].factor == "trend"
    assert "XAUUSD" in result.learning.last_fault

    reloaded = make_service(path).snapshot()
    assert reloaded.learning.observations == 1
    assert reloaded.learning.factor_performance[0].losses == 1


def test_daily_reports_and_fault_lessons_explain_paper_results(tmp_path: Path) -> None:
    service = make_service(tmp_path / "paper.json")
    first_day = datetime(2026, 1, 1, 10, tzinfo=UTC)
    second_day = datetime(2026, 1, 2, 10, tzinfo=UTC)

    service.process_cycle(scan(opportunity(), now=first_day), {}, "test-account", first_day)
    service.process_cycle(
        scan(opportunity(), now=first_day + timedelta(minutes=1)),
        {"XAUUSD": candle(low=100, high=102.2, close=101.8, now=first_day)},
        "test-account",
        first_day + timedelta(minutes=1),
    )
    service.process_cycle(scan(opportunity(), now=second_day), {}, "test-account", second_day)
    result = service.process_cycle(
        scan(opportunity(), now=second_day + timedelta(minutes=1)),
        {"XAUUSD": candle(low=98.8, high=102.2, close=100, now=second_day)},
        "test-account",
        second_day + timedelta(minutes=1),
    )

    reports = service._daily_reports(
        service._closed_trades(), days=3, as_of=second_day + timedelta(minutes=1)
    )

    assert reports[0].date == "2026-01-02"
    assert reports[0].winning_trades == 0
    assert reports[0].losing_trades == 1
    assert reports[0].losing_amount > 0
    assert reports[0].losing_pct > 0
    assert reports[0].net_pnl < 0
    assert reports[1].date == "2026-01-01"
    assert reports[1].winning_trades == 1
    assert reports[1].winning_amount > 0
    assert reports[1].win_rate_pct == 100
    assert result.learning.lessons[0].trade_id == result.closed_trades[0].id
    assert "stop" in result.learning.lessons[0].fault
    assert "collect" in result.learning.lessons[0].future_action
    assert "Collect" in result.learning.future_plan


def test_corrupt_primary_ledger_recovers_from_backup(tmp_path: Path) -> None:
    path = tmp_path / "paper.json"
    service = make_service(path)
    started = datetime(2026, 1, 1, tzinfo=UTC)
    service.process_cycle(scan(opportunity(), now=started), {}, "test-account", started)
    service.update_control(max_open_positions=9)

    path.write_text("{ damaged ledger", encoding="utf-8")
    recovered = make_service(path).snapshot()

    assert recovered.persistence.status == "recovered"
    assert recovered.metrics.open_positions == 1
