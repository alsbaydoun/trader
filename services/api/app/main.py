import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager, suppress
from threading import Lock

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from starlette.responses import Response

from app.brokers.mt5 import MT5Broker
from app.core.config import Settings, get_settings
from app.core.telemetry import (
    MT5_ACCOUNT_MATCH,
    MT5_CONNECTED,
    OPEN_POSITIONS,
    ORDERS_REJECTED,
    metrics_response,
)
from app.domain.models import Candle, Direction, OrderRequest, TradeMode
from app.domain.symbols import DEFAULT_SYMBOLS, get_symbol_profile
from app.schemas import (
    AccountListDTO,
    ActiveAccountRequestDTO,
    BacktestDTO,
    BrokerAccountDTO,
    CandleDTO,
    ExtremeBacktestDTO,
    ExtremeScanDTO,
    MarketScanDTO,
    MarketSymbolDTO,
    MT5ConnectionDTO,
    MT5PositionDTO,
    MT5QuoteDTO,
    NewsFeedDTO,
    OrderRequestDTO,
    PaperControlRequestDTO,
    PaperPortfolioDTO,
    PaperResetRequestDTO,
    PositionDTO,
    RiskDecisionDTO,
    ScanDTO,
    SignalDTO,
    StatusDTO,
    StrategyDTO,
    StrategyLabDTO,
)
from app.services.accounts import AccountRegistry, BrokerAccountProfile
from app.services.backtest import BacktestService
from app.services.extreme_backtest import ExtremeBacktestService
from app.services.extreme_paper_trading import ExtremePaperTradingService
from app.services.extreme_scanner import ExtremeScanResult, ExtremeSignalScanner
from app.services.jdub_traders import JdubTradersService
from app.services.market_data import MarketDataService
from app.services.market_scanner import MarketOpportunityScanner
from app.services.mt5_bridge import MT5ConnectionSnapshot, MT5ReadOnlyBridge
from app.services.news import NewsService
from app.services.paper_trading import PaperPortfolio, PaperTradingService
from app.services.risk import RiskEngine
from app.services.scanner import ScannerService
from app.services.strategy import SignalEngine
from app.services.strategy_lab import STRATEGY_PROFILES, ScalpStrategyLabService, StrategyLabMember

settings = get_settings()
market_data = MarketDataService()
signal_engine = SignalEngine()
news_service = NewsService(
    provider=settings.news_provider,
    calendar_file=settings.mt5_calendar_file,
)
backtests = BacktestService(signal_engine)
extreme_backtests = ExtremeBacktestService()
account_registry = AccountRegistry.from_settings(settings)
mt5_bridge = MT5ReadOnlyBridge(
    enabled=settings.mt5_read_only_enabled,
    timeout_ms=settings.mt5_timeout_ms,
)


def market_candles(symbol: str, timeframe: str, limit: int) -> list[Candle]:
    mt5_candles = mt5_bridge.candles(
        account_registry.active_account(),
        symbol,
        timeframe,
        limit,
    )
    if len(mt5_candles) >= 40:
        return mt5_candles
    return market_data.candles(symbol, timeframe, limit)


scanner = ScannerService(market_candles, signal_engine, news_service)
market_scanner = MarketOpportunityScanner(
    mt5_bridge,
    signal_engine,
    cache_seconds=settings.market_scan_cache_seconds,
)
extreme_scanner = ExtremeSignalScanner(
    mt5_bridge,
    cache_seconds=settings.extreme_scan_cache_seconds,
    alert_cooldown_seconds=settings.extreme_alert_cooldown_seconds,
)
paper_trader = PaperTradingService(
    settings.paper_state_file,
    enabled=settings.paper_auto_enabled,
    starting_balance=settings.paper_starting_balance,
    risk_per_trade_pct=settings.paper_risk_per_trade_pct,
    max_open_positions=settings.paper_max_open_positions,
    minimum_opportunity_score=settings.paper_min_opportunity_score,
    commission_bps=settings.paper_commission_bps,
    slippage_bps=settings.paper_slippage_bps,
    cycle_interval_seconds=settings.paper_cycle_interval_seconds,
    max_position_minutes=settings.paper_max_position_minutes,
    adaptive_learning_enabled=settings.paper_adaptive_learning_enabled,
    learning_min_samples=settings.paper_learning_min_samples,
)
jdub_trader = JdubTradersService(
    PaperTradingService(
        settings.jdub_paper_state_file,
        enabled=settings.jdub_paper_auto_enabled,
        starting_balance=settings.jdub_paper_starting_balance,
        risk_per_trade_pct=settings.jdub_paper_risk_per_trade_pct,
        max_open_positions=settings.jdub_paper_max_open_positions,
        minimum_opportunity_score=settings.jdub_paper_min_opportunity_score,
        commission_bps=settings.paper_commission_bps,
        slippage_bps=settings.paper_slippage_bps,
        cycle_interval_seconds=settings.jdub_paper_cycle_interval_seconds,
        max_position_minutes=settings.jdub_paper_max_position_minutes,
        adaptive_learning_enabled=settings.paper_adaptive_learning_enabled,
        learning_min_samples=settings.paper_learning_min_samples,
        trade_source="jdub-traders-virtual",
    ),
    mt5_bridge,
    settings.jdub_paper_session_state_file,
)
extreme_paper_trader = ExtremePaperTradingService(
    PaperTradingService(
        settings.extreme_paper_state_file,
        enabled=settings.extreme_paper_auto_enabled,
        starting_balance=settings.extreme_paper_starting_balance,
        risk_per_trade_pct=settings.extreme_paper_risk_per_trade_pct,
        max_open_positions=settings.extreme_paper_max_open_positions,
        minimum_opportunity_score=settings.extreme_paper_min_opportunity_score,
        commission_bps=settings.paper_commission_bps,
        slippage_bps=settings.paper_slippage_bps,
        cycle_interval_seconds=settings.extreme_scan_interval_seconds,
        max_position_minutes=settings.extreme_paper_max_position_minutes,
        adaptive_learning_enabled=settings.paper_adaptive_learning_enabled,
        learning_min_samples=settings.paper_learning_min_samples,
        trade_source="extreme-scanner-virtual",
    ),
    mt5_bridge,
    confirmed_only=settings.extreme_paper_confirmed_only,
)
strategy_lab = ScalpStrategyLabService(
    [
        StrategyLabMember(
            profile=profile,
            executor=ExtremePaperTradingService(
                PaperTradingService(
                    f"{settings.strategy_lab_state_dir}/{profile.id}.json",
                    enabled=settings.strategy_lab_enabled,
                    starting_balance=settings.strategy_lab_starting_balance,
                    risk_per_trade_pct=settings.strategy_lab_risk_per_trade_pct,
                    max_open_positions=settings.strategy_lab_max_open_positions,
                    minimum_opportunity_score=0.0,
                    commission_bps=settings.paper_commission_bps,
                    slippage_bps=settings.paper_slippage_bps,
                    cycle_interval_seconds=settings.strategy_lab_cycle_interval_seconds,
                    max_position_minutes=profile.max_minutes,
                    adaptive_learning_enabled=settings.strategy_lab_adaptive_learning_enabled,
                    learning_min_samples=settings.strategy_lab_learning_min_samples,
                    trade_source=f"strategy-lab-{profile.id}",
                ),
                mt5_bridge,
                confirmed_only=False,
            ),
        )
        for profile in STRATEGY_PROFILES
    ]
)
paper_cycle_lock = Lock()


def refresh_mt5_connection() -> MT5ConnectionSnapshot:
    active_account = account_registry.active_account()
    snapshot = mt5_bridge.probe(active_account)
    if active_account:
        account_registry.mark_connection_verified(
            active_account.id,
            snapshot.connection_verified,
        )
    MT5_CONNECTED.set(int(snapshot.terminal_connected))
    MT5_ACCOUNT_MATCH.set(int(snapshot.connection_verified))
    return snapshot


def account_dto(account: BrokerAccountProfile) -> BrokerAccountDTO:
    connection_verified = account_registry.connection_verified(account.id)
    return BrokerAccountDTO(
        id=account.id,
        provider=account.provider,
        server=account.server,
        account_type=account.account_type,
        login_masked=account.login_masked,
        active=account.id == account_registry.active_account_id,
        profile_configured=account.profile_configured,
        terminal_configured=account.terminal_configured,
        connection_verified=connection_verified,
        connection_ready=(
            account.profile_configured and account.terminal_configured and connection_verified
        ),
    )


def live_trading_unlocked() -> bool:
    active_account = account_registry.active_account()
    return bool(
        settings.live_trading_requested
        and not settings.mt5_read_only_enabled
        and active_account
        and account_dto(active_account).connection_ready
    )


def risk_engine(config: Settings = settings) -> RiskEngine:
    return RiskEngine(
        account_equity=config.account_equity,
        max_risk_per_trade_pct=config.max_risk_per_trade_pct,
        max_daily_loss_pct=config.max_daily_loss_pct,
        max_open_positions=config.max_open_positions,
        max_symbol_exposure_pct=config.max_symbol_exposure_pct,
    )


def broker() -> PaperTradingService | MT5Broker:
    if settings.broker_adapter == "mt5":
        return MT5Broker(live_trading_unlocked())
    return paper_trader


def run_paper_cycle(force: bool = False) -> PaperPortfolio:
    with paper_cycle_lock:
        account = account_registry.active_account()
        result = market_scanner.scan(
            account,
            paper_trader.timeframe,
            settings.market_scan_max_symbols,
            settings.market_scan_max_symbols,
            force,
        )
        if result.source != "mt5":
            paper_trader.record_error(
                "The virtual cycle was skipped because verified MT5 market data is unavailable."
            )
            return paper_trader.snapshot()
        prices: dict[str, Candle] = {}
        for position in paper_trader.positions():
            candles = mt5_bridge.candles(
                account,
                position.symbol,
                paper_trader.timeframe,
                80,
            )
            if candles:
                prices[position.symbol] = candles[-1]
        portfolio = paper_trader.process_cycle(
            result,
            prices,
            account.id if account else "",
        )
        OPEN_POSITIONS.set(portfolio.metrics.open_positions)
        return portfolio


def run_jdub_cycle(force: bool = False) -> PaperPortfolio:
    with paper_cycle_lock:
        account = account_registry.active_account()
        return jdub_trader.process_cycle(
            account,
            settings.market_scan_max_symbols,
            settings.market_scan_max_symbols,
            force=force,
        )


def run_extreme_cycle(
    force: bool = False,
    process_virtual_trades: bool = False,
) -> ExtremeScanResult:
    with paper_cycle_lock:
        account = account_registry.active_account()
        result = extreme_scanner.scan(
            account,
            extreme_paper_trader.timeframe if process_virtual_trades else paper_trader.timeframe,
            settings.market_scan_max_symbols,
            settings.market_scan_max_symbols,
            force,
        )
        if process_virtual_trades:
            extreme_paper_trader.process_scan(result, account)
            strategy_lab.process_scan(result, account)
        return result


def run_extreme_paper_cycle(force: bool = False) -> PaperPortfolio:
    run_extreme_cycle(force, process_virtual_trades=True)
    return extreme_paper_trader.snapshot()


async def paper_trading_loop() -> None:
    await asyncio.sleep(3)
    while True:
        if paper_trader.enabled:
            try:
                await asyncio.to_thread(run_paper_cycle)
            except Exception as exc:
                paper_trader.record_error(f"Virtual cycle failed: {exc}")
        await asyncio.sleep(paper_trader.cycle_interval_seconds)


async def jdub_trading_loop() -> None:
    await asyncio.sleep(12)
    while True:
        if jdub_trader.enabled:
            try:
                await asyncio.to_thread(run_jdub_cycle)
            except Exception as exc:
                jdub_trader.ledger.record_error(f"Jdub Traders virtual cycle failed: {exc}")
        await asyncio.sleep(jdub_trader.ledger.cycle_interval_seconds)


async def extreme_scanning_loop() -> None:
    await asyncio.sleep(8)
    while True:
        if settings.extreme_scan_enabled:
            with suppress(Exception):
                await asyncio.to_thread(
                    run_extreme_cycle,
                    False,
                    extreme_paper_trader.enabled or strategy_lab.enabled,
                )
        await asyncio.sleep(settings.extreme_scan_interval_seconds)


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    paper_task = asyncio.create_task(paper_trading_loop())
    jdub_task = asyncio.create_task(jdub_trading_loop())
    extreme_task = asyncio.create_task(extreme_scanning_loop())
    try:
        yield
    finally:
        paper_task.cancel()
        jdub_task.cancel()
        extreme_task.cancel()
        with suppress(asyncio.CancelledError):
            await paper_task
        with suppress(asyncio.CancelledError):
            await jdub_task
        with suppress(asyncio.CancelledError):
            await extreme_task
        mt5_bridge.shutdown()


app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
    description=(
        "AI trading workstation API with paper-first execution and live-trading guardrails."
    ),
    lifespan=lifespan,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/metrics")
def metrics() -> Response:
    return metrics_response()


@app.get("/status", response_model=StatusDTO)
def status() -> StatusDTO:
    active_account = account_registry.active_account()
    mt5_snapshot = refresh_mt5_connection()
    return StatusDTO(
        trading_mode=settings.trading_mode,
        broker_adapter=settings.broker_adapter,
        live_trading_enabled=settings.live_trading_enabled,
        live_trading_unlocked=live_trading_unlocked(),
        default_symbols=settings.symbols,
        guardrails={
            "max_risk_per_trade_pct": settings.max_risk_per_trade_pct,
            "max_daily_loss_pct": settings.max_daily_loss_pct,
            "max_open_positions": settings.max_open_positions,
            "max_symbol_exposure_pct": settings.max_symbol_exposure_pct,
        },
        broker_account=account_dto(active_account) if active_account else None,
        mt5=MT5ConnectionDTO.model_validate(mt5_snapshot),
    )


@app.get("/accounts", response_model=AccountListDTO)
def accounts() -> AccountListDTO:
    return AccountListDTO(
        active_account_id=account_registry.active_account_id,
        accounts=[account_dto(account) for account in account_registry.accounts()],
    )


@app.put("/accounts/active", response_model=AccountListDTO)
def set_active_account(payload: ActiveAccountRequestDTO) -> AccountListDTO:
    try:
        account_registry.set_active(payload.account_id)
    except KeyError as error:
        raise HTTPException(status_code=404, detail="Trading account was not found.") from error
    return accounts()


@app.get("/mt5/quotes", response_model=list[MT5QuoteDTO])
def mt5_quotes(
    symbols_query: str | None = Query(default=None, alias="symbols"),
) -> list[MT5QuoteDTO]:
    selected_symbols = (
        [symbol.strip() for symbol in symbols_query.split(",") if symbol.strip()]
        if symbols_query
        else settings.symbols
    )
    quotes = mt5_bridge.quotes(account_registry.active_account(), selected_symbols)
    return [MT5QuoteDTO.model_validate(quote) for quote in quotes]


@app.get("/mt5/positions", response_model=list[MT5PositionDTO])
def mt5_positions() -> list[MT5PositionDTO]:
    positions = mt5_bridge.positions(account_registry.active_account())
    return [MT5PositionDTO.model_validate(position) for position in positions]


@app.get("/symbols")
def symbols() -> list[dict[str, str | float]]:
    return [get_symbol_profile(symbol).__dict__ for symbol in DEFAULT_SYMBOLS]


@app.get("/market/symbols", response_model=list[MarketSymbolDTO])
def market_symbols(
    search: str = Query(default="", max_length=80),
    limit: int = Query(default=1000, ge=1, le=2000),
) -> list[MarketSymbolDTO]:
    catalog = mt5_bridge.market_symbols(account_registry.active_account())
    query = search.casefold().strip()
    if catalog:
        filtered = [
            symbol
            for symbol in catalog
            if not query
            or query in symbol.symbol.casefold()
            or query in symbol.description.casefold()
            or query in symbol.category.casefold()
        ]
        return [
            MarketSymbolDTO(
                symbol=symbol.symbol,
                description=symbol.description or symbol.symbol,
                category=symbol.category,
                currency_base=symbol.currency_base,
                currency_profit=symbol.currency_profit,
                digits=symbol.digits,
                bid=symbol.bid,
                ask=symbol.ask,
                spread_points=symbol.spread_points,
                visible=symbol.visible,
                trade_mode=symbol.trade_mode,
                last_tick_at=symbol.last_tick_at,
                source="mt5",
            )
            for symbol in filtered[:limit]
        ]

    configured = [get_symbol_profile(symbol) for symbol in settings.symbols]
    filtered_configured = [
        profile
        for profile in configured
        if not query
        or query in profile.symbol.casefold()
        or query in profile.display_name.casefold()
        or query in profile.asset_class.casefold()
    ]
    return [
        MarketSymbolDTO(
            symbol=profile.symbol,
            description=profile.display_name,
            category=profile.asset_class,
            currency_base="",
            currency_profit="USD",
            digits=0,
            bid=0.0,
            ask=0.0,
            spread_points=profile.default_spread_points,
            visible=True,
            trade_mode=0,
            last_tick_at=None,
            source="configured",
        )
        for profile in filtered_configured[:limit]
    ]


@app.get("/market/scan", response_model=MarketScanDTO)
def scan_market(
    timeframe: str = Query(default="1m"),
    limit: int = Query(default=30, ge=1, le=100),
    force: bool = Query(default=False),
) -> MarketScanDTO:
    result = market_scanner.scan(
        account_registry.active_account(),
        timeframe,
        settings.market_scan_max_symbols,
        limit,
        force,
    )
    return MarketScanDTO.model_validate(result)


@app.get("/extreme/scan", response_model=ExtremeScanDTO)
def scan_extreme_levels(
    timeframe: str = Query(default="1m"),
    limit: int = Query(default=50, ge=1, le=200),
    force: bool = Query(default=False),
) -> ExtremeScanDTO:
    result = extreme_scanner.scan(
        account_registry.active_account(),
        timeframe,
        settings.market_scan_max_symbols,
        limit,
        force,
    )
    return ExtremeScanDTO.model_validate(result)


@app.get("/strategy", response_model=StrategyDTO)
def strategy() -> StrategyDTO:
    return StrategyDTO.model_validate(signal_engine.definition())


@app.get("/paper/portfolio", response_model=PaperPortfolioDTO)
def paper_portfolio() -> PaperPortfolioDTO:
    return PaperPortfolioDTO.model_validate(paper_trader.snapshot())


@app.get("/paper/jdub/portfolio", response_model=PaperPortfolioDTO)
def jdub_paper_portfolio() -> PaperPortfolioDTO:
    return PaperPortfolioDTO.model_validate(jdub_trader.snapshot())


@app.get("/paper/extreme/portfolio", response_model=PaperPortfolioDTO)
def extreme_paper_portfolio() -> PaperPortfolioDTO:
    return PaperPortfolioDTO.model_validate(extreme_paper_trader.snapshot())


@app.get("/paper/strategies", response_model=StrategyLabDTO)
def paper_strategy_lab() -> StrategyLabDTO:
    return StrategyLabDTO.model_validate(strategy_lab.snapshot())


@app.post("/paper/control", response_model=PaperPortfolioDTO)
def control_paper_trading(payload: PaperControlRequestDTO) -> PaperPortfolioDTO:
    portfolio = paper_trader.update_control(
        enabled=payload.enabled,
        timeframe=payload.timeframe,
        minimum_opportunity_score=payload.minimum_opportunity_score,
        max_open_positions=payload.max_open_positions,
    )
    return PaperPortfolioDTO.model_validate(portfolio)


@app.post("/paper/jdub/control", response_model=PaperPortfolioDTO)
def control_jdub_paper_trading(payload: PaperControlRequestDTO) -> PaperPortfolioDTO:
    portfolio = jdub_trader.update_control(
        enabled=payload.enabled,
        timeframe=payload.timeframe,
        minimum_opportunity_score=payload.minimum_opportunity_score,
        max_open_positions=payload.max_open_positions,
    )
    return PaperPortfolioDTO.model_validate(portfolio)


@app.post("/paper/extreme/control", response_model=PaperPortfolioDTO)
def control_extreme_paper_trading(payload: PaperControlRequestDTO) -> PaperPortfolioDTO:
    portfolio = extreme_paper_trader.update_control(
        enabled=payload.enabled,
        timeframe=payload.timeframe,
        minimum_opportunity_score=payload.minimum_opportunity_score,
        max_open_positions=payload.max_open_positions,
    )
    return PaperPortfolioDTO.model_validate(portfolio)


@app.post("/paper/cycle", response_model=PaperPortfolioDTO)
def cycle_paper_trading(force: bool = Query(default=False)) -> PaperPortfolioDTO:
    return PaperPortfolioDTO.model_validate(run_paper_cycle(force))


@app.post("/paper/jdub/cycle", response_model=PaperPortfolioDTO)
def cycle_jdub_paper_trading(force: bool = Query(default=True)) -> PaperPortfolioDTO:
    return PaperPortfolioDTO.model_validate(run_jdub_cycle(force))


@app.post("/paper/extreme/cycle", response_model=PaperPortfolioDTO)
def cycle_extreme_paper_trading(force: bool = Query(default=True)) -> PaperPortfolioDTO:
    return PaperPortfolioDTO.model_validate(run_extreme_paper_cycle(force))


@app.post("/paper/strategies/cycle", response_model=StrategyLabDTO)
def cycle_paper_strategy_lab(force: bool = Query(default=True)) -> StrategyLabDTO:
    run_extreme_cycle(force, process_virtual_trades=True)
    return StrategyLabDTO.model_validate(strategy_lab.snapshot())


@app.post("/paper/strategies/{strategy_id}/control", response_model=StrategyLabDTO)
def control_paper_strategy(
    strategy_id: str,
    payload: PaperControlRequestDTO,
) -> StrategyLabDTO:
    try:
        snapshot = strategy_lab.update_control(
            strategy_id,
            enabled=payload.enabled,
            timeframe=payload.timeframe,
            minimum_opportunity_score=payload.minimum_opportunity_score,
            max_open_positions=payload.max_open_positions,
        )
    except KeyError as error:
        raise HTTPException(status_code=404, detail="Paper strategy was not found.") from error
    return StrategyLabDTO.model_validate(snapshot)


@app.post("/paper/strategies/{strategy_id}/reset", response_model=StrategyLabDTO)
def reset_paper_strategy(
    strategy_id: str,
    payload: PaperResetRequestDTO,
) -> StrategyLabDTO:
    if payload.confirmation != "RESET PAPER ACCOUNT":
        raise HTTPException(status_code=422, detail="Paper reset confirmation did not match.")
    try:
        snapshot = strategy_lab.reset(strategy_id)
    except KeyError as error:
        raise HTTPException(status_code=404, detail="Paper strategy was not found.") from error
    return StrategyLabDTO.model_validate(snapshot)


@app.post("/paper/positions/{trade_id}/close", response_model=PaperPortfolioDTO)
def close_paper_position(trade_id: str) -> PaperPortfolioDTO:
    position = next(
        (item for item in paper_trader.positions() if item.id == trade_id),
        None,
    )
    if position is None:
        raise HTTPException(status_code=404, detail="Open virtual position not found.")
    candles = mt5_bridge.candles(
        account_registry.active_account(),
        position.symbol,
        paper_trader.timeframe,
        80,
    )
    if not candles:
        raise HTTPException(
            status_code=409,
            detail="A verified current MT5 price is required to close the virtual position.",
        )
    return PaperPortfolioDTO.model_validate(
        paper_trader.close_trade(trade_id, candles[-1].close)
    )


@app.post("/paper/jdub/positions/{trade_id}/close", response_model=PaperPortfolioDTO)
def close_jdub_paper_position(trade_id: str) -> PaperPortfolioDTO:
    position = next(
        (item for item in jdub_trader.positions() if item.id == trade_id),
        None,
    )
    if position is None:
        raise HTTPException(status_code=404, detail="Open Jdub Traders virtual position not found.")
    candles = mt5_bridge.candles(
        account_registry.active_account(),
        position.symbol,
        jdub_trader.ledger.timeframe,
        80,
    )
    if not candles:
        raise HTTPException(
            status_code=409,
            detail="A verified current MT5 price is required to close the Jdub virtual position.",
        )
    return PaperPortfolioDTO.model_validate(
        jdub_trader.close_trade(trade_id, candles[-1].close)
    )


@app.post("/paper/extreme/positions/{trade_id}/close", response_model=PaperPortfolioDTO)
def close_extreme_paper_position(trade_id: str) -> PaperPortfolioDTO:
    position = next(
        (item for item in extreme_paper_trader.positions() if item.id == trade_id),
        None,
    )
    if position is None:
        raise HTTPException(status_code=404, detail="Open extreme virtual position not found.")
    candles = mt5_bridge.candles(
        account_registry.active_account(),
        position.symbol,
        extreme_paper_trader.timeframe,
        80,
    )
    if not candles:
        raise HTTPException(
            status_code=409,
            detail=(
                "A verified current MT5 price is required to close the extreme virtual position."
            ),
        )
    return PaperPortfolioDTO.model_validate(
        extreme_paper_trader.close_trade(trade_id, candles[-1].close)
    )


@app.post("/paper/reset", response_model=PaperPortfolioDTO)
def reset_paper_trading(payload: PaperResetRequestDTO) -> PaperPortfolioDTO:
    if payload.confirmation != "RESET PAPER ACCOUNT":
        raise HTTPException(status_code=422, detail="Paper reset confirmation did not match.")
    return PaperPortfolioDTO.model_validate(paper_trader.reset())


@app.post("/paper/jdub/reset", response_model=PaperPortfolioDTO)
def reset_jdub_paper_trading(payload: PaperResetRequestDTO) -> PaperPortfolioDTO:
    if payload.confirmation != "RESET PAPER ACCOUNT":
        raise HTTPException(status_code=422, detail="Paper reset confirmation did not match.")
    return PaperPortfolioDTO.model_validate(jdub_trader.reset())


@app.post("/paper/extreme/reset", response_model=PaperPortfolioDTO)
def reset_extreme_paper_trading(payload: PaperResetRequestDTO) -> PaperPortfolioDTO:
    if payload.confirmation != "RESET PAPER ACCOUNT":
        raise HTTPException(status_code=422, detail="Paper reset confirmation did not match.")
    return PaperPortfolioDTO.model_validate(extreme_paper_trader.reset())


@app.get("/candles/{symbol}", response_model=list[CandleDTO])
def candles(
    symbol: str,
    timeframe: str = Query(default="1m"),
    limit: int = Query(default=240, ge=40, le=2000),
) -> list[CandleDTO]:
    return [
        CandleDTO.model_validate(candle.__dict__)
        for candle in market_candles(symbol, timeframe, limit)
    ]


@app.get("/signals/{symbol}", response_model=SignalDTO)
def signal(symbol: str, timeframe: str = Query(default="1m")) -> SignalDTO:
    generated = signal_engine.generate(market_candles(symbol, timeframe, 240))
    return SignalDTO.model_validate(generated.__dict__)


@app.get("/scan", response_model=ScanDTO)
def scan(
    symbols_query: str | None = Query(default=None, alias="symbols"),
    timeframe: str = Query(default="1m"),
) -> ScanDTO:
    selected_symbols = (
        [symbol.strip() for symbol in symbols_query.split(",") if symbol.strip()]
        if symbols_query
        else settings.symbols
    )
    signals, news = scanner.scan(selected_symbols, timeframe)
    return ScanDTO(signals=signals, events=news.events, news_status=news.status)


@app.get("/news/analysis", response_model=NewsFeedDTO)
def news_analysis(
    symbols_query: str | None = Query(default=None, alias="symbols"),
) -> NewsFeedDTO:
    selected_symbols = (
        [symbol.strip() for symbol in symbols_query.split(",") if symbol.strip()]
        if symbols_query
        else settings.symbols
    )
    return NewsFeedDTO.model_validate(news_service.analysis_feed(selected_symbols))


@app.post("/risk/evaluate", response_model=RiskDecisionDTO)
def evaluate_risk(payload: OrderRequestDTO) -> RiskDecisionDTO:
    order = OrderRequest(
        symbol=payload.symbol,
        direction=Direction(payload.direction),
        volume=payload.volume,
        entry=payload.entry,
        stop_loss=payload.stop_loss,
        take_profit=payload.take_profit,
        mode=TradeMode(payload.mode),
    )
    decision = risk_engine().evaluate(order, broker().positions())
    return RiskDecisionDTO.model_validate(decision.__dict__)


@app.post("/orders", response_model=PositionDTO)
def place_order(payload: OrderRequestDTO) -> PositionDTO:
    if payload.mode == "signal_only":
        raise HTTPException(status_code=409, detail="Signal-only mode will not place orders.")
    if settings.trading_mode == "live" and not live_trading_unlocked():
        ORDERS_REJECTED.labels(reason="live_locked").inc()
        raise HTTPException(status_code=403, detail="Live trading is locked by configuration.")

    order = OrderRequest(
        symbol=payload.symbol,
        direction=Direction(payload.direction),
        volume=payload.volume,
        entry=payload.entry,
        stop_loss=payload.stop_loss,
        take_profit=payload.take_profit,
        mode=TradeMode(payload.mode),
    )
    decision = risk_engine().evaluate(order, broker().positions())
    if not decision.approved:
        ORDERS_REJECTED.labels(reason="risk").inc()
        raise HTTPException(status_code=422, detail=decision.reason)

    position = broker().place_order(order)
    OPEN_POSITIONS.set(len(broker().positions()))
    return PositionDTO.model_validate(position.__dict__)


@app.get("/positions", response_model=list[PositionDTO])
def positions() -> list[PositionDTO]:
    return [PositionDTO.model_validate(position.__dict__) for position in broker().positions()]


@app.get("/backtests/{symbol}", response_model=BacktestDTO)
def backtest(symbol: str, timeframe: str = Query(default="1m")) -> BacktestDTO:
    result = backtests.run(market_candles(symbol, timeframe, 500))
    return BacktestDTO.model_validate(result.__dict__)


@app.get("/backtests/extreme/{symbol}", response_model=ExtremeBacktestDTO)
def extreme_backtest(
    symbol: str,
    timeframe: str = Query(default="1m"),
    limit: int = Query(default=2000, ge=200, le=10000),
    max_hold_bars: int = Query(default=15, ge=1, le=240),
) -> ExtremeBacktestDTO:
    if timeframe != "1m":
        raise HTTPException(
            status_code=422,
            detail="TraderAI_M1_ExtremeScalp historical testing is available on the M1 timeframe.",
        )
    result = extreme_backtests.run(
        market_candles(symbol, timeframe, limit),
        max_hold_bars=max_hold_bars,
    )
    return ExtremeBacktestDTO.model_validate(result.__dict__)
