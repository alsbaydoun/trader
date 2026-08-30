import asyncio
import logging

from app.core.config import get_settings
from app.services.market_data import MarketDataService
from app.services.news import NewsService
from app.services.scanner import ScannerService
from app.services.strategy import SignalEngine

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("trader.worker")


async def main() -> None:
    settings = get_settings()
    demo_market_data = MarketDataService()
    scanner = ScannerService(demo_market_data.candles, SignalEngine(), NewsService())
    while True:
        signals, news = scanner.scan(settings.symbols, settings.default_timeframe)
        logger.info(
            "scan complete",
            extra={
                "signals": len(signals),
                "events": len(news.events),
                "news_state": news.status.state,
                "symbols": settings.symbols,
            },
        )
        await asyncio.sleep(15)


if __name__ == "__main__":
    asyncio.run(main())
