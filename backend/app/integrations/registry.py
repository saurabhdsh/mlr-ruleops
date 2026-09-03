from app.core.config import settings
from app.core.enums import IntegrationStatus


def integration_status() -> list[dict]:
    snow_ok = bool(settings.servicenow_base_url and settings.servicenow_username and settings.servicenow_password)
    jira_ok = bool(settings.jira_base_url and settings.jira_email and settings.jira_api_token)
    llm = settings.effective_llm_provider
    return [
        {
            "name": "Internal REST / webhook",
            "provider": "internal",
            "status": IntegrationStatus.ACTIVE,
            "notes": "POST /api/v1/integrations/webhook/ticket",
        },
        {
            "name": "ServiceNow",
            "provider": "servicenow",
            "status": IntegrationStatus.ACTIVE if snow_ok else IntegrationStatus.NOT_CONFIGURED,
            "notes": "Requires SERVICENOW_BASE_URL, USERNAME, PASSWORD",
        },
        {
            "name": "Jira",
            "provider": "jira",
            "status": IntegrationStatus.ACTIVE if jira_ok else IntegrationStatus.NOT_CONFIGURED,
            "notes": "Requires JIRA_BASE_URL, EMAIL, API_TOKEN",
        },
        {
            "name": "LLM provider",
            "provider": llm,
            "status": IntegrationStatus.ACTIVE,
            "notes": (
                "Local deterministic interpretation mode"
                if llm == "deterministic"
                else (
                    f"AWS Bedrock {settings.bedrock_model} via IAM/CLI profile {settings.aws_profile or 'default'}"
                    if llm == "bedrock"
                    else f"Remote provider {llm}"
                )
            ),
        },
        {
            "name": "PostgreSQL",
            "provider": "postgres",
            "status": IntegrationStatus.ACTIVE,
            "notes": settings.database_url.split("@")[-1] if "@" in settings.database_url else "configured",
        },
        {
            "name": "Redis",
            "provider": "redis",
            "status": IntegrationStatus.ACTIVE,
            "notes": settings.redis_url,
        },
    ]
