import json
from pathlib import Path
from threading import Lock

from pydantic import BaseModel, Field

from app.core.config import Settings


class BrokerAccountProfile(BaseModel):
    id: str = Field(min_length=3, pattern=r"^[a-z0-9-]+$")
    provider: str
    login: str = Field(min_length=4)
    server: str
    account_type: str
    terminal_path: str = ""
    symbol_map: dict[str, str] = Field(default_factory=dict)

    @property
    def login_masked(self) -> str:
        visible_digits = min(4, len(self.login))
        return f"{'*' * (len(self.login) - visible_digits)}{self.login[-visible_digits:]}"

    @property
    def profile_configured(self) -> bool:
        return bool(self.login and self.server)

    @property
    def terminal_configured(self) -> bool:
        return bool(self.terminal_path)


class AccountStore(BaseModel):
    active_account_id: str | None = None
    accounts: list[BrokerAccountProfile] = Field(default_factory=list)


class AccountRegistry:
    def __init__(
        self,
        path: Path | None,
        fallback_accounts: list[BrokerAccountProfile] | None = None,
    ) -> None:
        self.path = path
        self._lock = Lock()
        self._connection_verified: set[str] = set()
        self._store = self._load(fallback_accounts or [])
        self._normalize_active_account()

    @classmethod
    def from_settings(cls, settings: Settings) -> "AccountRegistry":
        path = Path(settings.mt5_accounts_file).expanduser() if settings.mt5_accounts_file else None
        fallback_accounts: list[BrokerAccountProfile] = []
        if settings.mt5_profile_configured:
            fallback_accounts.append(
                BrokerAccountProfile(
                    id=f"mt5-{settings.mt5_login}",
                    provider="JustMarkets",
                    login=settings.mt5_login,
                    server=settings.mt5_server,
                    account_type=settings.mt5_account_type,
                    terminal_path=settings.mt5_terminal_path,
                )
            )
        return cls(path, fallback_accounts)

    def accounts(self) -> list[BrokerAccountProfile]:
        return list(self._store.accounts)

    def active_account(self) -> BrokerAccountProfile | None:
        return next(
            (
                account
                for account in self._store.accounts
                if account.id == self._store.active_account_id
            ),
            None,
        )

    @property
    def active_account_id(self) -> str | None:
        return self._store.active_account_id

    def set_active(self, account_id: str) -> BrokerAccountProfile:
        account = next((item for item in self._store.accounts if item.id == account_id), None)
        if account is None:
            raise KeyError(account_id)
        with self._lock:
            self._store.active_account_id = account_id
            self._connection_verified.clear()
            self._persist()
        return account

    def connection_verified(self, account_id: str) -> bool:
        return account_id in self._connection_verified

    def mark_connection_verified(self, account_id: str, verified: bool) -> None:
        if verified:
            self._connection_verified.add(account_id)
        else:
            self._connection_verified.discard(account_id)

    def _load(self, fallback_accounts: list[BrokerAccountProfile]) -> AccountStore:
        if self.path and self.path.is_file():
            payload = json.loads(self.path.read_text(encoding="utf-8"))
            return AccountStore.model_validate(payload)
        active_id = fallback_accounts[0].id if fallback_accounts else None
        return AccountStore(active_account_id=active_id, accounts=fallback_accounts)

    def _normalize_active_account(self) -> None:
        account_ids = {account.id for account in self._store.accounts}
        if self._store.active_account_id not in account_ids:
            self._store.active_account_id = (
                self._store.accounts[0].id if self._store.accounts else None
            )

    def _persist(self) -> None:
        if self.path is None:
            return
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary_path = self.path.with_suffix(f"{self.path.suffix}.tmp")
        temporary_path.write_text(
            self._store.model_dump_json(indent=2) + "\n",
            encoding="utf-8",
        )
        temporary_path.replace(self.path)
