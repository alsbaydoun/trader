from dataclasses import dataclass


@dataclass(frozen=True)
class SymbolProfile:
    symbol: str
    display_name: str
    asset_class: str
    min_volume: float
    contract_size: float
    default_spread_points: float


DEFAULT_SYMBOLS: dict[str, SymbolProfile] = {
    "XAUUSD": SymbolProfile("XAUUSD", "Gold Spot", "metals", 0.01, 100.0, 24.0),
    "XAGUSD": SymbolProfile("XAGUSD", "Silver Spot", "metals", 0.01, 5000.0, 30.0),
    "BTCUSD": SymbolProfile("BTCUSD", "Bitcoin", "crypto", 0.01, 1.0, 45.0),
    "US100.std": SymbolProfile("US100.std", "Nasdaq 100 CFD", "indices", 0.01, 1.0, 18.0),
    "US30.std": SymbolProfile("US30.std", "Dow Jones CFD", "indices", 0.01, 1.0, 30.0),
    "WTI.m": SymbolProfile("WTI.m", "WTI Crude Oil", "energy", 0.01, 100.0, 6.0),
    "BRENT.m": SymbolProfile("BRENT.m", "Brent Crude Oil", "energy", 0.01, 100.0, 6.0),
}


def get_symbol_profile(symbol: str) -> SymbolProfile:
    return DEFAULT_SYMBOLS.get(
        symbol,
        SymbolProfile(symbol, symbol, "custom", 0.01, 1.0, 20.0),
    )
