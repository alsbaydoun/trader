import os
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from pathlib import Path

from app.services.news import MT5CalendarFileProvider, NewsAnalyzer, RawCalendarEvent


def raw_event(
    *,
    name: str,
    actual: float | None,
    forecast: float | None,
) -> RawCalendarEvent:
    return RawCalendarEvent(
        id="event-1",
        name=name,
        event_time=datetime.now(UTC) + timedelta(hours=1),
        country="United States",
        currency="USD",
        importance=3,
        sector="",
        source_url=None,
        actual=actual,
        forecast=forecast,
        previous=None,
        currency_impact=0,
    )


def test_pending_inflation_event_produces_conditional_symbol_analysis() -> None:
    analysis = NewsAnalyzer().analyze(
        raw_event(name="Consumer Price Index", actual=None, forecast=2.8),
        ["XAUUSD", "BTCUSD", "WTI.m"],
    )

    assert analysis.category == "Inflation"
    assert analysis.scope == "global"
    assert all(impact.direction == "mixed" for impact in analysis.impacts)
    assert "not known before" in analysis.analysis
    assert analysis.impacts[0].bullish_trigger
    assert analysis.risk_window.startswith("Avoid new entries 15 minutes")


def test_stronger_usd_labor_surprise_is_bearish_for_gold_and_bitcoin() -> None:
    analysis = NewsAnalyzer().analyze(
        raw_event(name="Nonfarm Payrolls", actual=300.0, forecast=200.0),
        ["XAUUSD", "BTCUSD"],
    )

    assert [impact.direction for impact in analysis.impacts] == ["bearish", "bearish"]
    assert "stronger or more hawkish" in analysis.analysis


def test_negative_calendar_currency_impact_maps_to_weaker_usd() -> None:
    event = raw_event(name="Federal Reserve Statement", actual=None, forecast=None)
    event = replace(event, currency_impact=2)

    analysis = NewsAnalyzer().analyze(event, ["XAUUSD"])

    assert analysis.impacts[0].direction == "bullish"
    assert "softer or more dovish" in analysis.analysis


def test_larger_oil_inventory_build_is_bearish_for_wti_and_brent() -> None:
    analysis = NewsAnalyzer().analyze(
        raw_event(name="Crude Oil Inventories", actual=4.0, forecast=1.0),
        ["WTI.m", "BRENT.m", "XAUUSD"],
    )

    assert [impact.direction for impact in analysis.impacts] == [
        "bearish",
        "bearish",
        "neutral",
    ]


def test_calendar_file_provider_reports_live_export(tmp_path: Path) -> None:
    event_time = int((datetime.now(UTC) + timedelta(hours=2)).timestamp())
    export = tmp_path / "calendar.csv"
    export.write_text(
        "value_id;event_time_utc;country;currency;importance;sector;name;source_url;"
        "actual;forecast;previous;currency_impact\n"
        f"42;{event_time};United States;USD;3;3;Consumer Price Index;;"
        ";2.8;2.7;0\n",
        encoding="utf-8",
    )
    os.utime(export, None)

    events, status = MT5CalendarFileProvider(str(export)).load()

    assert status.state == "live"
    assert status.calendar_connected is True
    assert events[0].name == "Consumer Price Index"
    assert events[0].actual is None
    assert events[0].forecast == 2.8
