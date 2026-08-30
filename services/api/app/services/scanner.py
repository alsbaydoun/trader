from collections.abc import Callable

from app.core.telemetry import SIGNALS_GENERATED
from app.domain.models import Candle, Signal
from app.services.news import NewsFeed, NewsService
from app.services.strategy import SignalEngine


class ScannerService:
    def __init__(
        self,
        candle_loader: Callable[[str, str, int], list[Candle]],
        signal_engine: SignalEngine,
        news_service: NewsService,
    ) -> None:
        self.candle_loader = candle_loader
        self.signal_engine = signal_engine
        self.news_service = news_service

    def scan(self, symbols: list[str], timeframe: str) -> tuple[list[Signal], NewsFeed]:
        signals = []
        for symbol in symbols:
            candles = self.candle_loader(symbol, timeframe, 240)
            signal = self.signal_engine.generate(candles)
            SIGNALS_GENERATED.labels(symbol=symbol).inc()
            signals.append(signal)
        return signals, self.news_service.analysis_feed(symbols)
