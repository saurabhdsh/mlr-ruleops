from app.ai.fallback import DeterministicFallbackProvider
from app.ai.provider import LLMProvider
from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger("ai.factory")


def get_llm_provider() -> LLMProvider:
    effective = settings.effective_llm_provider
    if effective == "openai":
        from app.ai.remote import OpenAIProvider

        logger.info("llm_provider_selected", provider="openai")
        return OpenAIProvider()
    if effective == "azure_openai":
        from app.ai.remote import AzureOpenAIProvider

        logger.info("llm_provider_selected", provider="azure_openai")
        return AzureOpenAIProvider()
    if effective == "anthropic":
        from app.ai.remote import AnthropicProvider

        logger.info("llm_provider_selected", provider="anthropic")
        return AnthropicProvider()
    if effective == "bedrock":
        try:
            from app.ai.bedrock import BedrockProvider

            logger.info("llm_provider_selected", provider="bedrock")
            return BedrockProvider()
        except Exception as exc:
            logger.warning("bedrock_unavailable_using_deterministic", error=str(exc)[:240])
            return DeterministicFallbackProvider()
    logger.info("llm_provider_selected", provider="deterministic", reason="configured_or_missing_credentials")
    return DeterministicFallbackProvider()
