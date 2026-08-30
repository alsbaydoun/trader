from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from importlib import import_module
from pathlib import Path
from threading import Lock
from typing import Any

from app.domain.models import Candle, Direction
from app.services.accounts import BrokerAccountProfile


@dataclass(frozen=True)
class MT5ConnectionSnapshot:
    status: str
    message: str
    read_only: bool
    package_available: bool
    initialized: bool
    terminal_connected: bool
    account_matches: bool
    server_matches: bool
    connection_verified: bool
    selected_login_masked: str
    terminal_login_masked: str
    terminal_server: str
    package_version: str
    terminal_version: str
    company: str
    currency: str
    leverage: int
    balance: float | None
    equity: float | None
    profit: float | None
    margin: float | None
    margin_free: float | None
    margin_level: float | None
    trade_allowed: bool
    expert_orders_allowed: bool
    symbols_count: int
    positions_count: int
    updated_at: datetime


@dataclass(frozen=True)
class MT5Quote:
    requested_symbol: str
    symbol: str
    bid: float
    ask: float
    spread: float
    digits: int
    visible: bool
    trade_mode: int
    updated_at: datetime


@dataclass(frozen=True)
class MT5PositionSnapshot:
    ticket: str
    symbol: str
    direction: Direction
    volume: float
    price_open: float
    price_current: float
    stop_loss: float | None
    take_profit: float | None
    profit: float
    opened_at: datetime


@dataclass(frozen=True)
class MT5MarketSymbol:
    symbol: str
    description: str
    category: str
    currency_base: str
    currency_profit: str
    digits: int
    point: float
    bid: float
    ask: float
    spread_points: float
    visible: bool
    trade_mode: int
    last_tick_at: datetime | None


class MT5ReadOnlyBridge:
    def __init__(
        self,
        enabled: bool,
        timeout_ms: int,
        module_loader: Callable[[], Any] | None = None,
    ) -> None:
        self.enabled = enabled
        self.timeout_ms = timeout_ms
        self._module_loader = module_loader or (lambda: import_module("MetaTrader5"))
        self._module: Any | None = None
        self._lock = Lock()

    def probe(self, account: BrokerAccountProfile | None) -> MT5ConnectionSnapshot:
        with self._lock:
            return self._probe_unlocked(account)

    def quotes(
        self,
        account: BrokerAccountProfile | None,
        symbols: list[str],
    ) -> list[MT5Quote]:
        with self._lock:
            snapshot = self._probe_unlocked(account)
            if not snapshot.connection_verified or self._module is None:
                return []
            quotes: list[MT5Quote] = []
            for requested_symbol in symbols:
                symbol = (
                    account.symbol_map.get(requested_symbol, requested_symbol)
                    if account
                    else requested_symbol
                )
                info = self._module.symbol_info(symbol)
                if info is not None and not bool(getattr(info, "visible", False)):
                    self._module.symbol_select(symbol, True)
                    info = self._module.symbol_info(symbol)
                tick = self._module.symbol_info_tick(symbol)
                if info is None or tick is None:
                    continue
                bid = float(getattr(tick, "bid", 0.0))
                ask = float(getattr(tick, "ask", 0.0))
                quotes.append(
                    MT5Quote(
                        requested_symbol=requested_symbol,
                        symbol=str(getattr(info, "name", symbol)),
                        bid=bid,
                        ask=ask,
                        spread=max(0.0, ask - bid),
                        digits=int(getattr(info, "digits", 0)),
                        visible=bool(getattr(info, "visible", False)),
                        trade_mode=int(getattr(info, "trade_mode", 0)),
                        updated_at=datetime.fromtimestamp(
                            int(getattr(tick, "time", 0)),
                            UTC,
                        ),
                    )
                )
            return quotes

    def positions(
        self,
        account: BrokerAccountProfile | None,
    ) -> list[MT5PositionSnapshot]:
        with self._lock:
            snapshot = self._probe_unlocked(account)
            if not snapshot.connection_verified or self._module is None:
                return []
            positions = self._module.positions_get() or ()
            return [self._position_snapshot(position) for position in positions]

    def market_symbols(
        self,
        account: BrokerAccountProfile | None,
    ) -> list[MT5MarketSymbol]:
        with self._lock:
            snapshot = self._probe_unlocked(account)
            if not snapshot.connection_verified or self._module is None:
                return []
            symbols = self._module.symbols_get() or ()
            return [self._market_symbol(info) for info in symbols if self._is_tradeable(info)]

    def scan_market_candles(
        self,
        account: BrokerAccountProfile | None,
        timeframe: str,
        limit: int,
        max_symbols: int,
    ) -> tuple[list[MT5MarketSymbol], dict[str, list[Candle]]]:
        with self._lock:
            snapshot = self._probe_unlocked(account)
            if not snapshot.connection_verified or self._module is None:
                return [], {}
            timeframe_value = self._timeframe_value(timeframe)
            if timeframe_value is None:
                return [], {}

            infos = [
                info for info in (self._module.symbols_get() or ()) if self._is_tradeable(info)
            ][:max_symbols]
            symbols: list[MT5MarketSymbol] = []
            candle_sets: dict[str, list[Candle]] = {}
            for info in infos:
                symbol = str(getattr(info, "name", ""))
                if not symbol:
                    continue
                was_visible = bool(getattr(info, "visible", False))
                if not was_visible:
                    self._module.symbol_select(symbol, True)
                rates = self._module.copy_rates_from_pos(symbol, timeframe_value, 0, limit + 1)
                refreshed_info = self._module.symbol_info(symbol) or info
                symbols.append(self._market_symbol(refreshed_info))
                if not was_visible:
                    self._module.symbol_select(symbol, False)
                if rates is None or len(rates) < 41:
                    continue
                candle_sets[symbol] = self._rates_to_candles(
                    symbol,
                    timeframe,
                    self._closed_rates(rates),
                )
            return symbols, candle_sets

    def candles(
        self,
        account: BrokerAccountProfile | None,
        symbol: str,
        timeframe: str,
        limit: int,
    ) -> list[Candle]:
        with self._lock:
            snapshot = self._probe_unlocked(account)
            if not snapshot.connection_verified or self._module is None or account is None:
                return []
            timeframe_value = self._timeframe_value(timeframe)
            if timeframe_value is None:
                return []
            broker_symbol = account.symbol_map.get(symbol, symbol)
            info = self._module.symbol_info(broker_symbol)
            if info is None:
                return []
            if not bool(getattr(info, "visible", False)):
                self._module.symbol_select(broker_symbol, True)
            rates = self._module.copy_rates_from_pos(
                broker_symbol,
                timeframe_value,
                0,
                limit + 1,
            )
            if rates is None:
                return []
            return self._rates_to_candles(symbol, timeframe, self._closed_rates(rates))

    def shutdown(self) -> None:
        with self._lock:
            if self._module is not None:
                self._module.shutdown()

    def _probe_unlocked(
        self,
        account: BrokerAccountProfile | None,
    ) -> MT5ConnectionSnapshot:
        now = datetime.now(UTC)
        if not self.enabled:
            return self._empty_snapshot(
                "disabled",
                "The read-only MT5 bridge is disabled by configuration.",
                account,
                now,
            )
        if account is None:
            return self._empty_snapshot(
                "no_account",
                "Select an MT5 account profile before connecting.",
                account,
                now,
            )
        if not account.terminal_path or not Path(account.terminal_path).is_file():
            return self._empty_snapshot(
                "terminal_missing",
                "The configured MetaTrader 5 terminal could not be found.",
                account,
                now,
            )
        try:
            module = self._load_module()
        except ImportError:
            return self._empty_snapshot(
                "package_unavailable",
                "The MetaTrader5 Python bridge package is not installed on this Windows host.",
                account,
                now,
            )
        initialized = bool(module.initialize(account.terminal_path, timeout=self.timeout_ms))
        if not initialized:
            return self._empty_snapshot(
                "initialize_failed",
                f"MT5 initialization failed: {self._last_error(module)}",
                account,
                now,
                package_available=True,
            )

        terminal = module.terminal_info()
        account_info = module.account_info()
        terminal_connected = bool(terminal and getattr(terminal, "connected", False))
        if not terminal_connected:
            return self._empty_snapshot(
                "terminal_disconnected",
                "MetaTrader 5 is open but is not connected to a trade server.",
                account,
                now,
                package_available=True,
                initialized=True,
            )
        if account_info is None:
            return self._empty_snapshot(
                "account_unavailable",
                f"MT5 account information is unavailable: {self._last_error(module)}",
                account,
                now,
                package_available=True,
                initialized=True,
                terminal_connected=True,
            )

        actual_login = str(getattr(account_info, "login", ""))
        actual_server = str(getattr(account_info, "server", ""))
        login_matches = actual_login == account.login
        server_matches = actual_server.casefold() == account.server.casefold()
        actual_login_masked = self._mask_login(actual_login)
        connection_verified = login_matches and server_matches
        if not login_matches:
            status = "account_mismatch"
            message = (
                f"MT5 is signed into {actual_login_masked}; select that profile or switch MT5 "
                f"to {account.login_masked}."
            )
        elif not server_matches:
            status = "server_mismatch"
            message = f"MT5 is connected to {actual_server}, not {account.server}."
        else:
            status = "connected"
            message = "The selected account matches the connected MT5 terminal."

        terminal_version = module.version()
        version_text = (
            f"{terminal_version[0]}.{terminal_version[1]} ({terminal_version[2]})"
            if terminal_version
            else ""
        )
        return MT5ConnectionSnapshot(
            status=status,
            message=message,
            read_only=True,
            package_available=True,
            initialized=True,
            terminal_connected=True,
            account_matches=login_matches,
            server_matches=server_matches,
            connection_verified=connection_verified,
            selected_login_masked=account.login_masked,
            terminal_login_masked=actual_login_masked,
            terminal_server=actual_server,
            package_version=str(getattr(module, "__version__", "")),
            terminal_version=version_text,
            company=str(getattr(account_info, "company", "")),
            currency=str(getattr(account_info, "currency", "")),
            leverage=int(getattr(account_info, "leverage", 0)),
            balance=self._optional_float(account_info, "balance"),
            equity=self._optional_float(account_info, "equity"),
            profit=self._optional_float(account_info, "profit"),
            margin=self._optional_float(account_info, "margin"),
            margin_free=self._optional_float(account_info, "margin_free"),
            margin_level=self._optional_float(account_info, "margin_level"),
            trade_allowed=bool(getattr(account_info, "trade_allowed", False)),
            expert_orders_allowed=bool(getattr(account_info, "trade_expert", False)),
            symbols_count=int(module.symbols_total()),
            positions_count=int(module.positions_total()),
            updated_at=now,
        )

    def _load_module(self) -> Any:
        if self._module is None:
            self._module = self._module_loader()
        return self._module

    def _timeframe_value(self, timeframe: str) -> Any | None:
        if self._module is None:
            return None
        timeframe_name = {
            "1m": "TIMEFRAME_M1",
            "5m": "TIMEFRAME_M5",
            "15m": "TIMEFRAME_M15",
            "1h": "TIMEFRAME_H1",
            "4h": "TIMEFRAME_H4",
            "1d": "TIMEFRAME_D1",
        }.get(timeframe)
        return getattr(self._module, timeframe_name, None) if timeframe_name else None

    @staticmethod
    def _rates_to_candles(symbol: str, timeframe: str, rates: Any) -> list[Candle]:
        return [
            Candle(
                symbol=symbol,
                timeframe=timeframe,
                ts=datetime.fromtimestamp(int(rate["time"]), UTC),
                open=float(rate["open"]),
                high=float(rate["high"]),
                low=float(rate["low"]),
                close=float(rate["close"]),
                volume=float(rate["tick_volume"]),
                source="mt5",
            )
            for rate in rates
        ]

    @staticmethod
    def _closed_rates(rates: Any) -> Any:
        """Drop MT5 position zero, which is the still-forming candle."""
        try:
            return rates[:-1] if len(rates) > 1 else rates
        except TypeError:
            return rates

    @staticmethod
    def _is_tradeable(info: Any) -> bool:
        return bool(getattr(info, "name", "")) and int(getattr(info, "trade_mode", 0)) > 0

    @staticmethod
    def _market_symbol(info: Any) -> MT5MarketSymbol:
        point = float(getattr(info, "point", 0.0))
        bid = float(getattr(info, "bid", 0.0))
        ask = float(getattr(info, "ask", 0.0))
        spread_points = float(getattr(info, "spread", 0.0))
        if spread_points <= 0 and point > 0 and ask >= bid:
            spread_points = (ask - bid) / point
        path = str(getattr(info, "path", ""))
        category = path.split("\\", maxsplit=1)[0] if path else "Other"
        tick_time = int(getattr(info, "time", 0))
        return MT5MarketSymbol(
            symbol=str(getattr(info, "name", "")),
            description=str(getattr(info, "description", "")),
            category=category,
            currency_base=str(getattr(info, "currency_base", "")),
            currency_profit=str(getattr(info, "currency_profit", "")),
            digits=int(getattr(info, "digits", 0)),
            point=point,
            bid=bid,
            ask=ask,
            spread_points=max(0.0, spread_points),
            visible=bool(getattr(info, "visible", False)),
            trade_mode=int(getattr(info, "trade_mode", 0)),
            last_tick_at=datetime.fromtimestamp(tick_time, UTC) if tick_time > 0 else None,
        )

    @staticmethod
    def _last_error(module: Any) -> str:
        error = module.last_error()
        if isinstance(error, tuple) and len(error) >= 2:
            return f"{error[0]} {error[1]}"
        return str(error)

    @staticmethod
    def _mask_login(login: str) -> str:
        if not login:
            return ""
        visible_digits = min(4, len(login))
        return f"{'*' * (len(login) - visible_digits)}{login[-visible_digits:]}"

    @staticmethod
    def _optional_float(source: Any, name: str) -> float | None:
        value = getattr(source, name, None)
        return float(value) if value is not None else None

    @staticmethod
    def _position_snapshot(position: Any) -> MT5PositionSnapshot:
        return MT5PositionSnapshot(
            ticket=str(getattr(position, "ticket", "")),
            symbol=str(getattr(position, "symbol", "")),
            direction=Direction.buy if int(getattr(position, "type", 0)) == 0 else Direction.sell,
            volume=float(getattr(position, "volume", 0.0)),
            price_open=float(getattr(position, "price_open", 0.0)),
            price_current=float(getattr(position, "price_current", 0.0)),
            stop_loss=(float(position.sl) if getattr(position, "sl", 0.0) else None),
            take_profit=(float(position.tp) if getattr(position, "tp", 0.0) else None),
            profit=float(getattr(position, "profit", 0.0)),
            opened_at=datetime.fromtimestamp(int(getattr(position, "time", 0)), UTC),
        )

    @staticmethod
    def _empty_snapshot(
        status: str,
        message: str,
        account: BrokerAccountProfile | None,
        updated_at: datetime,
        *,
        package_available: bool = False,
        initialized: bool = False,
        terminal_connected: bool = False,
    ) -> MT5ConnectionSnapshot:
        return MT5ConnectionSnapshot(
            status=status,
            message=message,
            read_only=True,
            package_available=package_available,
            initialized=initialized,
            terminal_connected=terminal_connected,
            account_matches=False,
            server_matches=False,
            connection_verified=False,
            selected_login_masked=account.login_masked if account else "",
            terminal_login_masked="",
            terminal_server="",
            package_version="",
            terminal_version="",
            company="",
            currency="",
            leverage=0,
            balance=None,
            equity=None,
            profit=None,
            margin=None,
            margin_free=None,
            margin_level=None,
            trade_allowed=False,
            expert_orders_allowed=False,
            symbols_count=0,
            positions_count=0,
            updated_at=updated_at,
        )
