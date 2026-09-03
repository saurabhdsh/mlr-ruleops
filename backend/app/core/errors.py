from typing import Any


class RuleOpsError(Exception):
    def __init__(
        self,
        code: str,
        message: str,
        context: dict[str, Any] | None = None,
        retryable: bool = False,
        status_code: int = 400,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.context = context or {}
        self.retryable = retryable
        self.status_code = status_code


class LowAIConfidence(RuleOpsError):
    def __init__(self, message: str, context: dict[str, Any] | None = None) -> None:
        super().__init__("LOW_AI_CONFIDENCE", message, context, False, 422)


class RuleNotFound(RuleOpsError):
    def __init__(self, message: str, context: dict[str, Any] | None = None) -> None:
        super().__init__("RULE_NOT_FOUND", message, context, False, 404)


class MultipleRulesAmbiguous(RuleOpsError):
    def __init__(self, message: str, context: dict[str, Any] | None = None) -> None:
        super().__init__("MULTIPLE_RULES_AMBIGUOUS", message, context, False, 409)


class CitationNotVerified(RuleOpsError):
    def __init__(self, message: str, context: dict[str, Any] | None = None) -> None:
        super().__init__("CITATION_NOT_VERIFIED", message, context, False, 422)


class ValidationFailed(RuleOpsError):
    def __init__(self, message: str, context: dict[str, Any] | None = None) -> None:
        super().__init__("VALIDATION_FAILED", message, context, False, 422)


class RegressionFailed(RuleOpsError):
    def __init__(self, message: str, context: dict[str, Any] | None = None) -> None:
        super().__init__("REGRESSION_FAILED", message, context, False, 422)


class ApprovalRequired(RuleOpsError):
    def __init__(self, message: str, context: dict[str, Any] | None = None) -> None:
        super().__init__("APPROVAL_REQUIRED", message, context, False, 403)


class StaleBaseVersion(RuleOpsError):
    def __init__(self, message: str, context: dict[str, Any] | None = None) -> None:
        super().__init__("STALE_BASE_VERSION", message, context, False, 409)


class DeploymentFailed(RuleOpsError):
    def __init__(self, message: str, context: dict[str, Any] | None = None) -> None:
        super().__init__("DEPLOYMENT_FAILED", message, context, False, 500)


class ForbiddenAction(RuleOpsError):
    def __init__(self, message: str = "Insufficient privileges") -> None:
        super().__init__("FORBIDDEN", message, {}, False, 403)


class Unauthorized(RuleOpsError):
    def __init__(self, message: str = "Authentication required") -> None:
        super().__init__("UNAUTHORIZED", message, {}, False, 401)


class IllegalTransition(RuleOpsError):
    def __init__(self, current: str, target: str) -> None:
        super().__init__(
            "ILLEGAL_WORKFLOW_TRANSITION",
            f"Cannot transition from {current} to {target}",
            {"current": current, "target": target},
            False,
            409,
        )
