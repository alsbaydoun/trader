from dataclasses import dataclass
from datetime import UTC, datetime

from app.services.accounts import BrokerAccountProfile
from app.services.extreme_paper_trading import ExtremePaperTradingService
from app.services.extreme_scanner import ExtremeReading, ExtremeScanResult
from app.services.paper_trading import PaperPortfolio


@dataclass(frozen=True)
class ScalpStrategyProfile:
    id: str
    name: str
    summary: str
    upper_level: float
    lower_level: float
    target_r: float
    stop_atr: float
    max_minutes: int
    criteria: list[str]

    def qualifies(self, reading: ExtremeReading) -> bool:
        if reading.level == "upper_85" and reading.score >= self.upper_level:
            return self._upper_confirmation(reading)
        if reading.level == "lower_15" and reading.score <= self.lower_level:
            return self._lower_confirmation(reading)
        return False

    def _upper_confirmation(self, reading: ExtremeReading) -> bool:
        return False

    def _lower_confirmation(self, reading: ExtremeReading) -> bool:
        return False


class ExtremeReversionProfile(ScalpStrategyProfile):
    def _upper_confirmation(self, reading: ExtremeReading) -> bool:
        return (
            reading.reversal_confirmed
            and reading.candle_direction == "bearish"
            and reading.rsi3 <= 75
            and reading.macd_histogram <= 0
        )

    def _lower_confirmation(self, reading: ExtremeReading) -> bool:
        return (
            reading.reversal_confirmed
            and reading.candle_direction == "bullish"
            and reading.rsi3 >= 25
            and reading.macd_histogram >= 0
        )


class ConfirmedPullbackProfile(ScalpStrategyProfile):
    def _upper_confirmation(self, reading: ExtremeReading) -> bool:
        return (
            reading.reversal_confirmed
            and reading.candle_direction == "bearish"
            and reading.rsi3 < 82
            and (reading.ema_fast < reading.ema_slow or reading.macd_histogram < 0)
        )

    def _lower_confirmation(self, reading: ExtremeReading) -> bool:
        return (
            reading.reversal_confirmed
            and reading.candle_direction == "bullish"
            and reading.rsi3 > 18
            and (reading.ema_fast > reading.ema_slow or reading.macd_histogram > 0)
        )


class MomentumReleaseProfile(ScalpStrategyProfile):
    def _upper_confirmation(self, reading: ExtremeReading) -> bool:
        return (
            reading.reversal_confirmed
            and reading.candle_direction == "bearish"
            and reading.rsi3 < 70
            and reading.rsi7 < 65
            and reading.momentum_pct < 0
        )

    def _lower_confirmation(self, reading: ExtremeReading) -> bool:
        return (
            reading.reversal_confirmed
            and reading.candle_direction == "bullish"
            and reading.rsi3 > 30
            and reading.rsi7 > 35
            and reading.momentum_pct > 0
        )


class RegimeAlignedPullbackProfile(ScalpStrategyProfile):
    """Only accepts an extreme after the short-term reversal agrees with the regime."""

    def _upper_confirmation(self, reading: ExtremeReading) -> bool:
        return (
            reading.reversal_confirmed
            and reading.candle_direction == "bearish"
            and reading.rsi3 < 70
            and reading.rsi7 < 60
            and reading.momentum_pct < 0
            and reading.macd_histogram < 0
            and reading.ema_fast < reading.ema_slow
        )

    def _lower_confirmation(self, reading: ExtremeReading) -> bool:
        return (
            reading.reversal_confirmed
            and reading.candle_direction == "bullish"
            and reading.rsi3 > 30
            and reading.rsi7 > 40
            and reading.momentum_pct > 0
            and reading.macd_histogram > 0
            and reading.ema_fast > reading.ema_slow
        )


STRATEGY_PROFILES: tuple[ScalpStrategyProfile, ...] = (
    ExtremeReversionProfile(
        id="extreme-reversion-90-10",
        name="90/10 Extreme Reversion",
        summary=(
            "Strict M1 mean-reversion scalp: the score must reach 90 or 10, then price must "
            "reject the extreme with short-term RSI and MACD histogram agreement."
        ),
        upper_level=90.0,
        lower_level=10.0,
        target_r=1.15,
        stop_atr=0.9,
        max_minutes=12,
        criteria=[
            "Composite score at least 90 for sells or at most 10 for buys",
            "Opposite-color rejection candle and RSI(3) leaving the extreme",
            "MACD histogram agrees with the reversal before entry",
        ],
    ),
    ConfirmedPullbackProfile(
        id="confirmed-pullback-85-15",
        name="Confirmed 85/15 Pullback",
        summary=(
            "Balanced M1 scalp that uses the existing 85/15 alert zones, but enters only after "
            "a rejection candle plus either EMA or MACD confirmation."
        ),
        upper_level=85.0,
        lower_level=15.0,
        target_r=1.25,
        stop_atr=1.0,
        max_minutes=15,
        criteria=[
            "Composite score at least 85 for sells or at most 15 for buys",
            "Rejection candle with RSI(3) moving back toward neutral",
            "EMA(5/6) or MACD histogram confirms direction",
        ],
    ),
    MomentumReleaseProfile(
        id="momentum-release-80-20",
        name="Momentum Release 80/20",
        summary=(
            "Selective M1 scalp that waits for an extreme and a measured momentum release, "
            "designed to avoid fading a move that is still accelerating."
        ),
        upper_level=80.0,
        lower_level=20.0,
        target_r=1.4,
        stop_atr=1.1,
        max_minutes=18,
        criteria=[
            "Composite score at least 80 for sells or at most 20 for buys",
            "RSI(3) and RSI(7) both move away from the extreme",
            "Four-candle momentum changes in the trade direction",
        ],
    ),
    RegimeAlignedPullbackProfile(
        id="regime-aligned-pullback",
        name="Regime-Aligned Pullback",
        summary=(
            "Most selective M1 scalp: an 85/15 alert is only tradable after rejection, "
            "RSI(3/7), momentum, MACD histogram, and EMA direction all agree."
        ),
        upper_level=85.0,
        lower_level=15.0,
        target_r=1.5,
        stop_atr=1.2,
        max_minutes=30,
        criteria=[
            "Composite score at least 85 for sells or at most 15 for buys",
            "Reversal candle plus RSI(3) and RSI(7) move away from the extreme",
            "Four-candle momentum and MACD histogram confirm the reversal",
            "EMA(5/6) agrees with the reversal direction",
        ],
    ),
)


@dataclass
class StrategyLabMember:
    profile: ScalpStrategyProfile
    executor: ExtremePaperTradingService
    candidates_last_cycle: int = 0


@dataclass(frozen=True)
class StrategyLabMemberSnapshot:
    id: str
    name: str
    summary: str
    upper_level: float
    lower_level: float
    target_r: float
    stop_atr: float
    max_minutes: int
    criteria: list[str]
    candidates_last_cycle: int
    portfolio: PaperPortfolio


@dataclass(frozen=True)
class StrategyLabSnapshot:
    source: str
    timeframe: str
    generated_at: datetime
    leader_strategy_id: str | None
    strategies: list[StrategyLabMemberSnapshot]
    main_lessons: list[str]
    disclaimer: str


class ScalpStrategyLabService:
    """Runs competing M1 scalp rules in isolated, persistent paper ledgers."""

    promotion_samples = 20

    def __init__(self, members: list[StrategyLabMember]) -> None:
        self.members = members
        self.source = "waiting"
        self.timeframe = "1m"
        self.generated_at = datetime.now(UTC)

    @property
    def enabled(self) -> bool:
        return any(member.executor.enabled for member in self.members)

    def process_scan(
        self,
        scan: ExtremeScanResult,
        account: BrokerAccountProfile | None,
    ) -> StrategyLabSnapshot:
        self.source = scan.source
        self.timeframe = scan.timeframe
        self.generated_at = scan.generated_at
        for member in self.members:
            candidates = (
                [reading for reading in scan.readings if member.profile.qualifies(reading)]
                if member.executor.enabled
                else []
            )
            member.candidates_last_cycle = len(candidates)
            member.executor.process_readings(
                scan,
                account,
                candidates,
                strategy_label=member.profile.name,
                stop_atr=member.profile.stop_atr,
                target_r=member.profile.target_r,
            )
        return self.snapshot()

    def snapshot(self) -> StrategyLabSnapshot:
        strategies = [
            StrategyLabMemberSnapshot(
                id=member.profile.id,
                name=member.profile.name,
                summary=member.profile.summary,
                upper_level=member.profile.upper_level,
                lower_level=member.profile.lower_level,
                target_r=member.profile.target_r,
                stop_atr=member.profile.stop_atr,
                max_minutes=member.profile.max_minutes,
                criteria=member.profile.criteria,
                candidates_last_cycle=member.candidates_last_cycle,
                portfolio=member.executor.snapshot(),
            )
            for member in self.members
        ]
        return StrategyLabSnapshot(
            source=self.source,
            timeframe=self.timeframe,
            generated_at=self.generated_at,
            leader_strategy_id=self._leader(strategies),
            strategies=strategies,
            main_lessons=self._lessons(strategies),
            disclaimer=(
                "The strategy lab is paper-only. It compares deterministic M1 scalp rules using "
                "observed prices, costs, stops, targets, and time limits. A good paper result is "
                "not a promise of future profit and never unlocks live MT5 orders."
            ),
        )

    def update_control(
        self,
        strategy_id: str,
        *,
        enabled: bool | None = None,
        timeframe: str | None = None,
        minimum_opportunity_score: float | None = None,
        max_open_positions: int | None = None,
    ) -> StrategyLabSnapshot:
        member = self._member(strategy_id)
        member.executor.update_control(
            enabled=enabled,
            timeframe=timeframe,
            minimum_opportunity_score=minimum_opportunity_score,
            max_open_positions=max_open_positions,
        )
        return self.snapshot()

    def reset(self, strategy_id: str) -> StrategyLabSnapshot:
        self._member(strategy_id).executor.reset()
        return self.snapshot()

    def _member(self, strategy_id: str) -> StrategyLabMember:
        for member in self.members:
            if member.profile.id == strategy_id:
                return member
        raise KeyError(strategy_id)

    def _leader(self, strategies: list[StrategyLabMemberSnapshot]) -> str | None:
        eligible = [
            item
            for item in strategies
            if item.portfolio.metrics.closed_trades >= self.promotion_samples
        ]
        if not eligible:
            return None
        return max(
            eligible,
            key=lambda item: (
                item.portfolio.metrics.profit_factor or 0.0,
                item.portfolio.metrics.win_rate,
                item.portfolio.metrics.total_return_pct,
            ),
        ).id

    def _lessons(self, strategies: list[StrategyLabMemberSnapshot]) -> list[str]:
        lessons = [
            (
                f"The main head is observing {len(strategies)} isolated paper strategies on "
                f"{self.timeframe}; no live strategy is changed by these results."
            )
        ]
        for strategy in strategies:
            learning = strategy.portfolio.learning
            if not learning.observations:
                lessons.append(
                    f"{strategy.name}: collecting outcomes; at least {self.promotion_samples} "
                    "closed trades are required before comparison can promote a leader."
                )
                continue
            win_rate = learning.wins / learning.observations * 100
            lessons.append(
                f"{strategy.name}: {learning.observations} outcomes, {win_rate:.1f}% wins; "
                f"{learning.recommendation}"
            )
            if learning.last_fault:
                lessons.append(f"Latest fault from {strategy.name}: {learning.last_fault}")
        leader = self._leader(strategies)
        if leader:
            leader_name = next(item.name for item in strategies if item.id == leader)
            lessons.append(
                f"Evidence leader: {leader_name}. This is a paper comparison only and is not "
                "automatically connected to the main account."
            )
        return lessons[:12]
