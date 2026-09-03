import re

CONTROL_CHARS = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")


def sanitize_text(value: str | None, max_len: int = 20000) -> str:
    if not value:
        return ""
    cleaned = CONTROL_CHARS.sub("", value)
    return cleaned[:max_len]


def redact_secrets(payload: dict) -> dict:
    redacted = {}
    secret_keys = {"password", "api_key", "token", "secret", "authorization"}
    for key, value in payload.items():
        if key.lower() in secret_keys or "password" in key.lower() or "token" in key.lower():
            redacted[key] = "***"
        elif isinstance(value, dict):
            redacted[key] = redact_secrets(value)
        else:
            redacted[key] = value
    return redacted
