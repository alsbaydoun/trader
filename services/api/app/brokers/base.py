from abc import ABC, abstractmethod

from app.domain.models import OrderRequest, Position


class Broker(ABC):
    @abstractmethod
    def positions(self) -> list[Position]:
        raise NotImplementedError

    @abstractmethod
    def place_order(self, order: OrderRequest) -> Position:
        raise NotImplementedError
