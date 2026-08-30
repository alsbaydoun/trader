import csv
import os
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Literal, cast

NewsState = Literal["live", "stale", "config_required", "error"]
ImpactDirection = Literal["bullish", "bearish", "mixed", "neutral"]


@dataclass(frozen=True)
class MarketImpact:
    symbol: str
    direction: ImpactDirection
    confidence: float
    horizon: str
    thesis: str
    causal_chain: list[str]
    bullish_trigger: str
    bearish_trigger: str
    invalidation: str


@dataclass(frozen=True)
class MarketEvent:
    id: str
    title: str
    category: str
    scope: Literal["global", "symbol"]
    symbols: list[str]
    severity: Literal["low", "medium", "high"]
    source: str
    source_url: str | None
    published_at: datetime
    event_time: datetime
    analysis: str
    why_it_matters: list[str]
    risk_window: str
    actual: float | None
    forecast: float | None
    previous: float | None
    impacts: list[MarketImpact]


@dataclass(frozen=True)
class NewsStatus:
    provider: str
    state: NewsState
    message: str
    calendar_connected: bool
    headlines_connected: bool
    updated_at: datetime


@dataclass(frozen=True)
class NewsFeed:
    status: NewsStatus
    events: list[MarketEvent]


@dataclass(frozen=True)
class RawCalendarEvent:
    id: str
    name: str
    event_time: datetime
    country: str
    currency: str
    importance: int
    sector: str
    source_url: str | None
    actual: float | None
    forecast: float | None
    previous: float | None
    currency_impact: int


class MT5CalendarFileProvider:
    def __init__(self, file_path: str = "", stale_after_minutes: int = 10) -> None:
        self.file_path = Path(file_path) if file_path else self.default_path()
        self.stale_after = timedelta(minutes=stale_after_minutes)

    @staticmethod
    def default_path() -> Path:
        app_data = Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming"))
        return app_data / "MetaQuotes" / "Terminal" / "Common" / "Files" / "TraderAI-calendar.csv"

    def load(self) -> tuple[list[RawCalendarEvent], NewsStatus]:
        now = datetime.now(UTC)
        if not self.file_path.is_file():
            return [], NewsStatus(
                provider="MT5 economic calendar",
                state="config_required",
                message=(
                    "Attach TraderCalendarBridge to one MT5 chart to enable scheduled-event "
                    "analysis. An external headline feed is still required for unscheduled news."
                ),
                calendar_connected=False,
                headlines_connected=False,
                updated_at=now,
            )

        modified_at = datetime.fromtimestamp(self.file_path.stat().st_mtime, UTC)
        try:
            events = self._read_events()
        except (OSError, UnicodeError, csv.Error, ValueError) as error:
            return [], NewsStatus(
                provider="MT5 economic calendar",
                state="error",
                message=f"The MT5 calendar export could not be read: {error}",
                calendar_connected=False,
                headlines_connected=False,
                updated_at=modified_at,
            )

        stale = now - modified_at > self.stale_after
        state: NewsState = "stale" if stale else "live"
        freshness = "stale" if stale else "connected"
        return events, NewsStatus(
            provider="MT5 economic calendar",
            state=state,
            message=(
                f"MT5 scheduled-event calendar is {freshness}. "
                "Unscheduled headline analysis needs a licensed news provider."
            ),
            calendar_connected=not stale,
            headlines_connected=False,
            updated_at=modified_at,
        )

    def _read_events(self) -> list[RawCalendarEvent]:
        with self.file_path.open(encoding="utf-8-sig", newline="") as file:
            rows = csv.DictReader(file, delimiter=";")
            required = {"value_id", "event_time_utc", "name", "importance"}
            if not rows.fieldnames or not required.issubset(rows.fieldnames):
                raise ValueError("calendar export has an unsupported header")
            events = [event for row in rows if (event := self._parse_row(row)) is not None]
        return events

    @staticmethod
    def _parse_row(row: dict[str, str]) -> RawCalendarEvent | None:
        name = row.get("name", "").strip()
        if not name:
            return None
        event_time = datetime.fromtimestamp(int(row["event_time_utc"]), UTC)
        return RawCalendarEvent(
            id=row["value_id"].strip(),
            name=name,
            event_time=event_time,
            country=row.get("country", "").strip(),
            currency=row.get("currency", "").strip(),
            importance=int(row.get("importance", "0") or 0),
            sector=row.get("sector", "").strip(),
            source_url=row.get("source_url", "").strip() or None,
            actual=_optional_float(row.get("actual")),
            forecast=_optional_float(row.get("forecast")),
            previous=_optional_float(row.get("previous")),
            currency_impact=int(row.get("currency_impact", "0") or 0),
        )


class NewsAnalyzer:
    def analyze(self, event: RawCalendarEvent, symbols: list[str]) -> MarketEvent:
        category = self._category(event)
        actual_bias = self._actual_bias(event, category)
        impacts = [
            self._symbol_impact(symbol, event, category, actual_bias) for symbol in symbols
        ]
        affected = [impact.symbol for impact in impacts if impact.direction != "neutral"]
        released = event.actual is not None
        severity = _severity(event.importance)
        return MarketEvent(
            id=event.id,
            title=event.name,
            category=category,
            scope="global" if len(affected) > 2 else "symbol",
            symbols=affected,
            severity=severity,
            source="MT5 economic calendar",
            source_url=event.source_url,
            published_at=event.event_time if released else datetime.now(UTC),
            event_time=event.event_time,
            analysis=self._global_analysis(event, category, actual_bias),
            why_it_matters=self._why_it_matters(category),
            risk_window=self._risk_window(event, severity),
            actual=event.actual,
            forecast=event.forecast,
            previous=event.previous,
            impacts=impacts,
        )

    @staticmethod
    def _category(event: RawCalendarEvent) -> str:
        text = f"{event.name} {event.sector}".lower()
        if any(word in text for word in ("crude oil", "petroleum", "oil stock", "inventory")):
            return "Energy inventory"
        central_bank_terms = ("interest rate", "fomc", "federal reserve", "fed ", "powell")
        if any(word in text for word in central_bank_terms):
            return "Central bank"
        inflation_terms = (
            "cpi",
            "pce",
            "inflation",
            "consumer price",
            "producer price",
            "ppi",
        )
        if any(word in text for word in inflation_terms):
            return "Inflation"
        if any(
            word in text
            for word in ("payroll", "employment", "unemployment", "jobless", "labor", "jobs")
        ):
            return "Labor"
        if any(word in text for word in ("gdp", "pmi", "retail", "industrial", "consumer")):
            return "Growth"
        return "Macro event"

    @staticmethod
    def _actual_bias(event: RawCalendarEvent, category: str) -> str:
        if event.actual is None or event.forecast is None:
            if event.currency_impact == 1:
                return "stronger_usd"
            if event.currency_impact == 2:
                return "weaker_usd"
            return "pending"
        delta = event.actual - event.forecast
        if abs(delta) < 1e-12:
            return "neutral"
        name = event.name.lower()
        if category == "Energy inventory":
            return "oil_bearish" if delta > 0 else "oil_bullish"
        inverse = any(word in name for word in ("unemployment", "jobless", "claims"))
        stronger = delta < 0 if inverse else delta > 0
        return "stronger_usd" if stronger else "weaker_usd"

    def _symbol_impact(
        self,
        symbol: str,
        event: RawCalendarEvent,
        category: str,
        actual_bias: str,
    ) -> MarketImpact:
        if category == "Energy inventory":
            return self._energy_impact(symbol, actual_bias)
        if event.currency and event.currency != "USD":
            return self._neutral_impact(symbol, event.currency)
        return self._usd_impact(symbol, category, actual_bias)

    @staticmethod
    def _energy_impact(symbol: str, bias: str) -> MarketImpact:
        if symbol not in {"WTI.m", "BRENT.m"}:
            return NewsAnalyzer._neutral_impact(symbol, "oil inventory")
        direction = cast(
            ImpactDirection,
            {"oil_bullish": "bullish", "oil_bearish": "bearish"}.get(bias, "mixed"),
        )
        confidence = 0.76 if direction != "mixed" else 0.42
        return MarketImpact(
            symbol=symbol,
            direction=direction,
            confidence=confidence,
            horizon="Immediate to intraday",
            thesis=(
                "A smaller-than-forecast build or a draw tightens the prompt supply signal."
                if direction == "bullish"
                else "A larger-than-forecast build loosens the prompt supply signal."
                if direction == "bearish"
                else "Direction depends on the inventory surprise and product-stock details."
            ),
            causal_chain=["Inventory surprise", "Supply balance repricing", f"{symbol} response"],
            bullish_trigger="A draw or materially smaller build than forecast.",
            bearish_trigger="A build or materially larger build than forecast.",
            invalidation="Product stocks, production, or risk sentiment contradict crude stocks.",
        )

    @staticmethod
    def _usd_impact(symbol: str, category: str, bias: str) -> MarketImpact:
        metals = symbol in {"XAUUSD", "XAGUSD"}
        risk_assets = symbol in {"BTCUSD", "US100.std", "US30.std"}
        energy = symbol in {"WTI.m", "BRENT.m"}
        if not (metals or risk_assets or energy):
            return NewsAnalyzer._neutral_impact(symbol, "USD macro")

        if bias == "pending":
            direction: ImpactDirection = "mixed"
        elif bias == "neutral":
            direction = "neutral"
        elif metals or risk_assets:
            direction = "bearish" if bias == "stronger_usd" else "bullish"
        else:
            direction = "mixed"

        if category == "Growth" and risk_assets and bias != "pending":
            direction = "mixed"
        confidence = 0.68 if direction in {"bullish", "bearish"} else 0.4
        if category == "Central bank":
            confidence = min(confidence + 0.08, 0.8)

        if metals:
            chain = ["USD/rate expectations", "Real yields and dollar", f"{symbol} repricing"]
            stronger = "Hotter or stronger data lifts rate expectations and the USD."
            weaker = "Softer data lowers rate expectations and the USD."
        elif risk_assets:
            chain = [
                "Policy/liquidity expectations",
                "Risk appetite and valuation",
                f"{symbol} repricing",
            ]
            stronger = "A hawkish surprise tightens financial conditions."
            weaker = "A dovish surprise eases financial conditions."
        else:
            chain = [
                "USD and growth expectations",
                "Demand versus currency effect",
                f"{symbol} repricing",
            ]
            stronger = "Strong growth supports demand, but a stronger USD can offset it."
            weaker = "Weak growth hurts demand, but a weaker USD can offset it."

        return MarketImpact(
            symbol=symbol,
            direction=direction,
            confidence=confidence,
            horizon="Immediate to one session",
            thesis=(
                stronger
                if bias == "stronger_usd"
                else weaker
                if bias == "weaker_usd"
                else "The release is pending; direction depends on the surprise versus forecast."
                if bias == "pending"
                else "The headline value is near forecast; details and revisions may dominate."
            ),
            causal_chain=chain,
            bullish_trigger=NewsAnalyzer._bullish_trigger(symbol),
            bearish_trigger=NewsAnalyzer._bearish_trigger(symbol),
            invalidation=(
                "Price, yields, or the USD fail to confirm after the first volatility spike."
            ),
        )

    @staticmethod
    def _neutral_impact(symbol: str, driver: str) -> MarketImpact:
        return MarketImpact(
            symbol=symbol,
            direction="neutral",
            confidence=0.2,
            horizon="Monitor",
            thesis=f"No direct {driver} transmission rule is configured for this instrument.",
            causal_chain=["Event", "Cross-market confirmation", symbol],
            bullish_trigger="A confirmed positive cross-market reaction.",
            bearish_trigger="A confirmed negative cross-market reaction.",
            invalidation="No sustained price or volatility response.",
        )

    @staticmethod
    def _bullish_trigger(symbol: str) -> str:
        if symbol in {"XAUUSD", "XAGUSD", "BTCUSD", "US100.std", "US30.std"}:
            return "Softer/dovish surprise with falling yields and a weaker USD."
        return "Growth demand improves without a destabilizing USD or risk-off move."

    @staticmethod
    def _bearish_trigger(symbol: str) -> str:
        if symbol in {"XAUUSD", "XAGUSD", "BTCUSD", "US100.std", "US30.std"}:
            return "Hotter/hawkish surprise with rising yields and a stronger USD."
        return "Demand expectations weaken or the USD shock dominates."

    @staticmethod
    def _global_analysis(event: RawCalendarEvent, category: str, bias: str) -> str:
        if bias == "pending":
            return (
                f"This {category.lower()} release is a volatility risk window. Direction is not "
                "known before the actual value, revisions, and market confirmation arrive."
            )
        if bias == "stronger_usd":
            return (
                "The result is stronger or more hawkish than forecast, which can lift the USD and "
                "rate expectations. Confirm with yields and price before acting."
            )
        if bias == "weaker_usd":
            return (
                "The result is softer or more dovish than forecast, which can lower the USD and "
                "rate expectations. Confirm with yields and price before acting."
            )
        if bias == "oil_bullish":
            return "The inventory surprise points to tighter near-term oil supply than expected."
        if bias == "oil_bearish":
            return "The inventory surprise points to looser near-term oil supply than expected."
        return "The headline is close to forecast; revisions and underlying details matter more."

    @staticmethod
    def _why_it_matters(category: str) -> list[str]:
        reasons = {
            "Central bank": [
                "Changes rate and liquidity expectations",
                "Can reprice every USD-linked asset",
            ],
            "Inflation": [
                "Changes the expected path of interest rates",
                "Moves yields, USD, metals, and indices",
            ],
            "Labor": [
                "Changes growth and rate expectations",
                "Often causes fast two-way volatility",
            ],
            "Growth": [
                "Changes earnings and demand expectations",
                "Rate and growth effects can conflict",
            ],
            "Energy inventory": [
                "Updates the near-term supply balance",
                "Most directly affects WTI and Brent",
            ],
            "Macro event": [
                "Can change USD and risk sentiment",
                "Requires cross-market confirmation",
            ],
        }
        return reasons[category]

    @staticmethod
    def _risk_window(event: RawCalendarEvent, severity: str) -> str:
        if event.event_time > datetime.now(UTC):
            minutes = 15 if severity == "high" else 5
            return f"Avoid new entries {minutes} minutes before; wait for spreads to normalize."
        return "Treat the first move as provisional until price, spread, USD, and yields confirm."


class NewsService:
    def __init__(self, provider: str = "auto", calendar_file: str = "") -> None:
        self.provider_name = provider
        self.provider = MT5CalendarFileProvider(calendar_file)
        self.analyzer = NewsAnalyzer()

    def analysis_feed(self, symbols: list[str]) -> NewsFeed:
        raw_events, status = self.provider.load()
        if self.provider_name not in {"auto", "mt5_calendar", "mock"}:
            status = NewsStatus(
                provider=self.provider_name,
                state="config_required",
                message=(
                    f"News provider '{self.provider_name}' is not implemented. "
                    "Use the MT5 calendar bridge or add a licensed provider adapter."
                ),
                calendar_connected=False,
                headlines_connected=False,
                updated_at=datetime.now(UTC),
            )
            return NewsFeed(status=status, events=[])

        now = datetime.now(UTC)
        relevant = [
            event
            for event in raw_events
            if now - timedelta(hours=24) <= event.event_time <= now + timedelta(days=7)
        ]
        relevant.sort(
            key=lambda event: (
                0 if event.event_time >= now else 1,
                -event.importance,
                abs((event.event_time - now).total_seconds()),
            )
        )
        events = [self.analyzer.analyze(event, symbols) for event in relevant[:16]]
        return NewsFeed(status=status, events=events)

    def latest_events(self, symbols: list[str]) -> list[MarketEvent]:
        return self.analysis_feed(symbols).events


def _optional_float(value: str | None) -> float | None:
    if value is None or not value.strip():
        return None
    return float(value)


def _severity(importance: int) -> Literal["low", "medium", "high"]:
    if importance >= 3:
        return "high"
    if importance == 2:
        return "medium"
    return "low"
