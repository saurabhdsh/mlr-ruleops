from typing import Any

import httpx

from app.core.config import settings
from app.core.errors import RuleOpsError
from app.integrations.base import TicketProvider


class JiraTicketProvider(TicketProvider):
    name = "jira"

    def __init__(self) -> None:
        if not (settings.jira_base_url and settings.jira_email and settings.jira_api_token):
            raise RuleOpsError("INTEGRATION_NOT_CONFIGURED", "Jira is NOT_CONFIGURED", status_code=503)
        self.base = settings.jira_base_url.rstrip("/")
        self.auth = (settings.jira_email, settings.jira_api_token)

    def get_ticket(self, external_id: str) -> dict[str, Any]:
        resp = httpx.get(f"{self.base}/rest/api/3/issue/{external_id}", auth=self.auth, timeout=20)
        resp.raise_for_status()
        return resp.json()

    def create_comment(self, external_id: str, body: str) -> None:
        httpx.post(
            f"{self.base}/rest/api/3/issue/{external_id}/comment",
            auth=self.auth,
            json={"body": body},
            timeout=20,
        ).raise_for_status()

    def update_status(self, external_id: str, status: str) -> None:
        resp = httpx.get(
            f"{self.base}/rest/api/3/issue/{external_id}/transitions",
            auth=self.auth,
            timeout=20,
        )
        resp.raise_for_status()
        wanted = (status or "").strip().lower()
        match = None
        for tr in resp.json().get("transitions") or []:
            name = (tr.get("name") or "").strip().lower()
            to_name = ((tr.get("to") or {}).get("name") or "").strip().lower()
            if wanted in {name, to_name} or wanted.replace("_", " ") in {name, to_name}:
                match = tr
                break
        if match is None:
            raise RuleOpsError(
                "JIRA_TRANSITION_NOT_FOUND",
                f"No Jira transition matches status '{status}'",
                {"external_id": external_id, "status": status},
                False,
                422,
            )
        httpx.post(
            f"{self.base}/rest/api/3/issue/{external_id}/transitions",
            auth=self.auth,
            json={"transition": {"id": match["id"]}},
            timeout=20,
        ).raise_for_status()

    def add_attachment(self, external_id: str, filename: str, content: str) -> None:
        httpx.post(
            f"{self.base}/rest/api/3/issue/{external_id}/attachments",
            auth=self.auth,
            files={"file": (filename, content.encode())},
            headers={"X-Atlassian-Token": "no-check"},
            timeout=20,
        ).raise_for_status()
