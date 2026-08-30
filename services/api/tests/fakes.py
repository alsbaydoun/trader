from types import SimpleNamespace
from typing import Any


class FakeMetaTrader:
    __version__ = "5.0.test"
    TIMEFRAME_M1 = 1
    TIMEFRAME_M5 = 5
    TIMEFRAME_M15 = 15
    TIMEFRAME_H1 = 60
    TIMEFRAME_H4 = 240
    TIMEFRAME_D1 = 1440

    def __init__(
        self,
        *,
        login: str = "1000000002",
        server: str = "JustMarkets-Live",
        initialize_result: bool = True,
        connected: bool = True,
    ) -> None:
        self.login = login
        self.server = server
        self.initialize_result = initialize_result
        self.connected = connected
        self.shutdown_called = False

    def initialize(self, path: str, *, timeout: int) -> bool:
        return bool(path and timeout and self.initialize_result)

    def terminal_info(self) -> Any:
        return SimpleNamespace(connected=self.connected)

    def account_info(self) -> Any:
        return SimpleNamespace(
            login=int(self.login),
            server=self.server,
            company="JustMarkets",
            currency="USD",
            leverage=500,
            balance=1000.0,
            equity=995.0,
            profit=-5.0,
            margin=10.0,
            margin_free=985.0,
            margin_level=9950.0,
            trade_allowed=True,
            trade_expert=True,
        )

    def version(self) -> tuple[int, int, str]:
        return (500, 6140, "test")

    def symbols_total(self) -> int:
        return 272

    def positions_total(self) -> int:
        return 1

    def symbol_info(self, symbol: str) -> Any:
        return next(
            (info for info in self.symbols_get() if info.name == symbol),
            None,
        )

    def symbols_get(self) -> tuple[Any, ...]:
        return (
            SimpleNamespace(
                name="XAUUSD",
                description="Gold Spot",
                path=r"Metals\Spot",
                currency_base="XAU",
                currency_profit="USD",
                digits=2,
                point=0.01,
                bid=2350.5,
                ask=2350.7,
                spread=20,
                visible=True,
                trade_mode=4,
                time=2000000000,
            ),
            SimpleNamespace(
                name="BTCUSD",
                description="Bitcoin",
                path=r"Crypto\Majors",
                currency_base="BTC",
                currency_profit="USD",
                digits=2,
                point=0.01,
                bid=64000.0,
                ask=64010.0,
                spread=1000,
                visible=False,
                trade_mode=4,
                time=2000000000,
            ),
        )

    def symbol_select(self, symbol: str, selected: bool) -> bool:
        return bool(symbol and selected)

    def symbol_info_tick(self, symbol: str) -> Any:
        if symbol != "XAUUSD":
            return None
        return SimpleNamespace(bid=2350.5, ask=2350.7, time=1700000000)

    def copy_rates_from_pos(
        self,
        symbol: str,
        timeframe: int,
        start: int,
        count: int,
    ) -> list[dict[str, float]] | None:
        if symbol not in {"XAUUSD", "BTCUSD"} or not timeframe or start != 0:
            return None
        base = 2300.0 if symbol == "XAUUSD" else 64000.0
        return [
            {
                "time": 1700000000 + index * 60,
                "open": base + index * 0.1,
                "high": base + 1.0 + index * 0.1,
                "low": base - 1.0 + index * 0.1,
                "close": base + 0.5 + index * 0.1,
                "tick_volume": 100.0 + index,
            }
            for index in range(count)
        ]

    def positions_get(self) -> tuple[Any, ...]:
        return (
            SimpleNamespace(
                ticket=123,
                symbol="XAUUSD",
                type=0,
                volume=0.01,
                price_open=2345.0,
                price_current=2350.5,
                sl=2335.0,
                tp=2370.0,
                profit=5.5,
                time=1700000000,
            ),
        )

    def last_error(self) -> tuple[int, str]:
        return (1, "Success")

    def shutdown(self) -> None:
        self.shutdown_called = True
