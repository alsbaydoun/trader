from datetime import UTC, datetime
from pathlib import Path

from app.services.extreme_scanner import ExtremeReading, ExtremeScanResult
from app.services.strategy_lab import STRATEGY_PROFILES, ScalpStrategyLabService, StrategyLabMember
from tests.test_extreme_paper_trading import CandleBridge, account, make_service


def reading(
    *, score: float, level: str, candle_direction: str, momentum_pct: float
) -> ExtremeReading:
    now = datetime(2026, 1, 1, tzinfo=UTC)
    return ExtremeReading(
        symbol="XAUUSD",
        price=100.0,
        score=score,
        level=level,
        rsi1=100.0 if level == "upper_85" else 0.0,
        macd=-0.2 if level == "upper_85" else 0.2,
        macd_signal=-0.1 if level == "upper_85" else 0.1,
        macd_histogram=-0.1 if level == "upper_85" else 0.1,
        ema_fast=99.0 if level == "upper_85" else 101.0,
        ema_slow=100.0,
        recommendation="paper test",
        reasons=["paper test"],
        source="mt5",
        detected_at=now,
        rsi3=70.0 if level == "upper_85" else 30.0,
        rsi7=60.0 if level == "upper_85" else 40.0,
        momentum_pct=momentum_pct,
        candle_direction=candle_direction,
        atr_pct=0.4,
        reversal_confirmed=True,
    )


def scan(reading_item: ExtremeReading) -> ExtremeScanResult:
    now = datetime(2026, 1, 1, tzinfo=UTC)
    return ExtremeScanResult(
        source="mt5",
        timeframe="1m",
        available_symbols=1,
        scanned_symbols=1,
        generated_at=now,
        upper_level=85.0,
        lower_level=15.0,
        readings=[reading_item],
        alerts=[],
        recent_alerts=[],
        disclaimer="paper test",
    )


def test_strict_reversion_requires_rejection_confirmation() -> None:
    profile = STRATEGY_PROFILES[0]
    setup = reading(score=95.0, level="upper_85", candle_direction="bullish", momentum_pct=0.1)
    trigger = reading(score=95.0, level="upper_85", candle_direction="bearish", momentum_pct=-0.1)

    assert profile.qualifies(setup) is False
    assert profile.qualifies(trigger) is True


def test_strategy_lab_uses_an_isolated_virtual_ledger(tmp_path: Path) -> None:
    bridge = CandleBridge()
    executor = make_service(tmp_path / "lab.json", bridge)
    lab = ScalpStrategyLabService([StrategyLabMember(STRATEGY_PROFILES[0], executor)])

    result = lab.process_scan(
        scan(reading(score=95.0, level="upper_85", candle_direction="bearish", momentum_pct=-0.1)),
        account(),
    )

    member = result.strategies[0]
    assert result.timeframe == "1m"
    assert member.candidates_last_cycle == 1
    assert member.portfolio.metrics.open_positions == 1
    assert member.portfolio.open_positions[0].source == "extreme-scanner-virtual"
    assert result.leader_strategy_id is None
