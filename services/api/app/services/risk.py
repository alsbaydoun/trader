from app.domain.models import Direction, OrderRequest, Position, RiskDecision


class RiskEngine:
    def __init__(
        self,
        account_equity: float,
        max_risk_per_trade_pct: float,
        max_daily_loss_pct: float,
        max_open_positions: int,
        max_symbol_exposure_pct: float,
    ) -> None:
        self.account_equity = account_equity
        self.max_risk_per_trade_pct = max_risk_per_trade_pct
        self.max_daily_loss_pct = max_daily_loss_pct
        self.max_open_positions = max_open_positions
        self.max_symbol_exposure_pct = max_symbol_exposure_pct

    def evaluate(
        self,
        order: OrderRequest,
        open_positions: list[Position],
        realized_daily_loss: float = 0.0,
    ) -> RiskDecision:
        if order.direction == Direction.hold:
            return RiskDecision(False, "Hold signals cannot be executed.", 0.0)
        if order.volume <= 0:
            return RiskDecision(False, "Order volume must be greater than zero.", 0.0)
        if order.stop_loss is None:
            return RiskDecision(False, "A stop loss is required for every executable order.", 0.0)
        if len(open_positions) >= self.max_open_positions:
            return RiskDecision(False, "Maximum open positions limit reached.", 0.0)

        max_daily_loss = self.account_equity * (self.max_daily_loss_pct / 100)
        if realized_daily_loss >= max_daily_loss:
            return RiskDecision(False, "Daily loss guard has locked trading.", 0.0)

        risk_per_unit = abs(order.entry - order.stop_loss)
        if risk_per_unit <= 0:
            return RiskDecision(False, "Stop loss must be away from entry.", 0.0)

        max_cash_risk = self.account_equity * (self.max_risk_per_trade_pct / 100)
        max_volume_by_risk = max_cash_risk / risk_per_unit
        same_symbol_volume = sum(
            position.volume for position in open_positions if position.symbol == order.symbol
        )
        max_symbol_volume = self.account_equity * (self.max_symbol_exposure_pct / 100) / order.entry
        remaining_symbol_volume = max(0.0, max_symbol_volume - same_symbol_volume)
        max_volume = max(0.0, min(max_volume_by_risk, remaining_symbol_volume))

        if order.volume > max_volume:
            return RiskDecision(
                False,
                f"Requested volume exceeds risk limit. Maximum allowed is {max_volume:.4f}.",
                round(max_volume, 4),
            )

        return RiskDecision(True, "Approved by configured risk guardrails.", round(max_volume, 4))
