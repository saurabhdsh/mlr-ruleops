from abc import ABC, abstractmethod
from typing import Any


class TicketProvider(ABC):
    name: str

    @abstractmethod
    def get_ticket(self, external_id: str) -> dict[str, Any]:
        raise NotImplementedError

    @abstractmethod
    def create_comment(self, external_id: str, body: str) -> None:
        raise NotImplementedError

    @abstractmethod
    def update_status(self, external_id: str, status: str) -> None:
        raise NotImplementedError

    @abstractmethod
    def add_attachment(self, external_id: str, filename: str, content: str) -> None:
        raise NotImplementedError
