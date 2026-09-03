from typing import Any

from app.integrations.base import TicketProvider


class InternalTicketProvider(TicketProvider):
    name = "internal"

    def get_ticket(self, external_id: str) -> dict[str, Any]:
        return {"external_id": external_id, "source": "INTERNAL"}

    def create_comment(self, external_id: str, body: str) -> None:
        return None

    def update_status(self, external_id: str, status: str) -> None:
        return None

    def add_attachment(self, external_id: str, filename: str, content: str) -> None:
        return None
