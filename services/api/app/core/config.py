from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Trader AI Workstation"
    trading_mode: str = Field(default="paper", pattern="^(paper|live)$")
    broker_adapter: str = Field(default="paper")
    live_trading_enabled: bool = False
    live_trading_acknowledgement: str = ""
    live_trading_required_ack: str = "I understand live trading can lose money"

    default_symbols: str = "XAUUSD,XAGUSD,BTCUSD,US100.std,US30.std,WTI.m,BRENT.m"
    default_timeframe: str = "1m"
    max_risk_per_trade_pct: float = 0.5
    max_daily_loss_pct: float = 2.0
    max_open_positions: int = 3
    max_symbol_exposure_pct: float = 5.0
    account_equity: float = 10000.0
    market_scan_max_symbols: int = Field(default=500, ge=10, le=2000)
    market_scan_cache_seconds: int = Field(default=300, ge=15, le=3600)

    paper_auto_enabled: bool = True
    paper_state_file: str = "../../data/paper-regime-trading.json"
    paper_starting_balance: float = Field(default=10000.0, gt=0)
    paper_risk_per_trade_pct: float = Field(default=0.05, ge=0.01, le=2.0)
    paper_max_open_positions: int = Field(default=3, ge=1, le=200)
    paper_min_opportunity_score: float = Field(default=62.0, ge=0.0, le=100.0)
    paper_commission_bps: float = Field(default=1.0, ge=0.0, le=100.0)
    paper_slippage_bps: float = Field(default=1.0, ge=0.0, le=100.0)
    paper_cycle_interval_seconds: int = Field(default=60, ge=15, le=3600)
    paper_max_position_minutes: int = Field(default=120, ge=1, le=43200)
    paper_adaptive_learning_enabled: bool = True
    paper_learning_min_samples: int = Field(default=8, ge=3, le=1000)

    jdub_paper_auto_enabled: bool = True
    jdub_paper_state_file: str = "../../data/jdub-traders-paper.json"
    jdub_paper_session_state_file: str = "../../data/jdub-traders-sessions.json"
    jdub_paper_starting_balance: float = Field(default=10000.0, gt=0)
    jdub_paper_risk_per_trade_pct: float = Field(default=0.05, ge=0.01, le=2.0)
    jdub_paper_max_open_positions: int = Field(default=3, ge=1, le=200)
    jdub_paper_min_opportunity_score: float = Field(default=65.0, ge=0.0, le=100.0)
    jdub_paper_cycle_interval_seconds: int = Field(default=60, ge=15, le=3600)
    jdub_paper_max_position_minutes: int = Field(default=90, ge=1, le=43200)

    extreme_paper_auto_enabled: bool = True
    extreme_paper_state_file: str = "../../data/extreme-pullback-trading.json"
    extreme_paper_starting_balance: float = Field(default=10000.0, gt=0)
    extreme_paper_risk_per_trade_pct: float = Field(default=0.05, ge=0.01, le=2.0)
    extreme_paper_max_open_positions: int = Field(default=3, ge=1, le=200)
    extreme_paper_min_opportunity_score: float = Field(default=70.0, ge=0.0, le=100.0)
    extreme_paper_confirmed_only: bool = True
    extreme_paper_max_position_minutes: int = Field(default=60, ge=1, le=43200)

    strategy_lab_enabled: bool = True
    strategy_lab_state_dir: str = "../../data/strategy-lab"
    strategy_lab_starting_balance: float = Field(default=10000.0, gt=0)
    strategy_lab_risk_per_trade_pct: float = Field(default=0.05, ge=0.01, le=2.0)
    strategy_lab_max_open_positions: int = Field(default=10, ge=1, le=200)
    strategy_lab_cycle_interval_seconds: int = Field(default=15, ge=10, le=3600)
    strategy_lab_adaptive_learning_enabled: bool = True
    strategy_lab_learning_min_samples: int = Field(default=8, ge=3, le=1000)

    extreme_scan_enabled: bool = True
    extreme_scan_cache_seconds: int = Field(default=10, ge=5, le=300)
    extreme_scan_interval_seconds: int = Field(default=15, ge=10, le=3600)
    extreme_alert_cooldown_seconds: int = Field(default=300, ge=30, le=86400)

    news_provider: str = "auto"
    news_api_key: str = ""
    mt5_calendar_file: str = ""
    openai_api_key: str = ""

    mt5_login: str = ""
    mt5_password: str = ""
    mt5_server: str = ""
    mt5_account_type: str = ""
    mt5_terminal_path: str = ""
    mt5_accounts_file: str = ""
    mt5_read_only_enabled: bool = True
    mt5_timeout_ms: int = Field(default=10000, ge=1000, le=60000)

    model_config = SettingsConfigDict(
        env_file=(".env", "../../.env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @property
    def symbols(self) -> list[str]:
        return [symbol.strip() for symbol in self.default_symbols.split(",") if symbol.strip()]

    @property
    def mt5_profile_configured(self) -> bool:
        return bool(self.mt5_login and self.mt5_server)

    @property
    def mt5_credentials_configured(self) -> bool:
        return self.mt5_profile_configured and bool(self.mt5_password)

    @property
    def mt5_connection_configured(self) -> bool:
        return self.mt5_credentials_configured and bool(self.mt5_terminal_path)

    @property
    def mt5_login_masked(self) -> str:
        if not self.mt5_login:
            return ""
        visible_digits = min(4, len(self.mt5_login))
        return f"{'*' * (len(self.mt5_login) - visible_digits)}{self.mt5_login[-visible_digits:]}"

    @property
    def live_trading_unlocked(self) -> bool:
        return (
            self.trading_mode == "live"
            and self.live_trading_enabled
            and self.live_trading_acknowledgement == self.live_trading_required_ack
            and self.broker_adapter == "mt5"
            and self.mt5_connection_configured
            and not self.mt5_read_only_enabled
        )

    @property
    def live_trading_requested(self) -> bool:
        return (
            self.trading_mode == "live"
            and self.live_trading_enabled
            and self.live_trading_acknowledgement == self.live_trading_required_ack
            and self.broker_adapter == "mt5"
        )


@lru_cache
def get_settings() -> Settings:
    return Settings()
