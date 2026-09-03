from typing import Any

import httpx

from app.core.config import settings
from app.core.errors import RuleOpsError
from app.integrations.base import TicketProvider


class ServiceNowTicketProvider(TicketProvider):
    name = "servicenow"

    def __init__(self) -> None:
        if not (settings.servicenow_base_url and settings.servicenow_username and settings.servicenow_password):
            raise RuleOpsError("INTEGRATION_NOT_CONFIGURED", "ServiceNow is NOT_CONFIGURED", status_code=503)
        self.base = settings.servicenow_base_url.rstrip("/")
        self.auth = (settings.servicenow_username, settings.servicenow_password)

    def get_ticket(self, external_id: str) -> dict[str, Any]:
        resp = httpx.get(
            f"{self.base}/api/now/table/incident/{external_id}",
            auth=self.auth,
            timeout=20,
        )
        resp.raise_for_status()
        return resp.json()

    def create_comment(self, external_id: str, body: str) -> None:
        httpx.patch(
            f"{self.base}/api/now/table/incident/{external_id}",
            auth=self.auth,
            json={"comments": body},
            timeout=20,
        ).raise_for_status()

    def update_status(self, external_id: str, status: str) -> None:
        httpx.patch(
            f"{self.base}/api/now/table/incident/{external_id}",
            auth=self.auth,
            json={"state": status},
            timeout=20,
        ).raise_for_status()

    def add_attachment(self, external_id: str, filename: str, content: str) -> None:
        httpx.post(
            f"{self.base}/api/now/attachment/file",
            params={"table_name": "incident", "table_sys_id": external_id, "file_name": filename},
            auth=self.auth,
            content=content.encode(),
            timeout=20,
        ).raise_for_status()
