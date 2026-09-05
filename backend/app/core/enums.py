from enum import StrEnum


class RoleName(StrEnum):
    ADMIN = "ADMIN"
    MLR_ADMIN = "MLR_ADMIN"
    MEDICAL_REVIEWER = "MEDICAL_REVIEWER"
    REGULATORY_REVIEWER = "REGULATORY_REVIEWER"
    BUSINESS_REQUESTER = "BUSINESS_REQUESTER"
    AUDITOR = "AUDITOR"
    VIEWER = "VIEWER"


class TicketPriority(StrEnum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class WorkflowState(StrEnum):
    RECEIVED = "RECEIVED"
    NORMALIZED = "NORMALIZED"
    INTERPRETING = "INTERPRETING"
    NEEDS_CLARIFICATION = "NEEDS_CLARIFICATION"
    RULE_RESOLVING = "RULE_RESOLVING"
    RULE_RESOLVED = "RULE_RESOLVED"
    PROPOSING_CHANGE = "PROPOSING_CHANGE"
    PROPOSAL_READY = "PROPOSAL_READY"
    VALIDATING = "VALIDATING"
    VALIDATION_FAILED = "VALIDATION_FAILED"
    SANDBOXING = "SANDBOXING"
    TESTING = "TESTING"
    REGRESSION_FAILED = "REGRESSION_FAILED"
    IMPACT_ANALYSIS = "IMPACT_ANALYSIS"
    RISK_ASSESSMENT = "RISK_ASSESSMENT"
    AWAITING_APPROVAL = "AWAITING_APPROVAL"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    DEPLOYING = "DEPLOYING"
    DEPLOYED = "DEPLOYED"
    DEPLOYMENT_FAILED = "DEPLOYMENT_FAILED"
    ROLLED_BACK = "ROLLED_BACK"
    CLOSED = "CLOSED"


class RuleScopeType(StrEnum):
    UNIVERSAL = "UNIVERSAL"
    MARKET = "MARKET"
    BRAND = "BRAND"
    MARKET_BRAND = "MARKET_BRAND"
    SCIENTIFIC_ACCURACY = "SCIENTIFIC_ACCURACY"


class RuleType(StrEnum):
    TEXT = "TEXT"
    LOGIC = "LOGIC"


class RuleStatus(StrEnum):
    DRAFT = "DRAFT"
    ACTIVE = "ACTIVE"
    SUPERSEDED = "SUPERSEDED"
    RETIRED = "RETIRED"


class ChangeType(StrEnum):
    TEXT_STRING_UPDATE = "TEXT_STRING_UPDATE"
    BUSINESS_LOGIC_CHANGE = "BUSINESS_LOGIC_CHANGE"
    AMBIGUOUS_INCOMPLETE = "AMBIGUOUS_INCOMPLETE"
    ROLLBACK_REQUEST = "ROLLBACK_REQUEST"


class HitlGate(StrEnum):
    GATE1_INTENT_CONFIRM = "Gate1-IntentConfirm"
    GATE2_RULE_MATCH = "Gate2-RuleMatch"
    GATE3_SINGLE_APPROVAL = "Gate3-SingleApproval"
    GATE3_DUAL_APPROVAL = "Gate3-DualApproval"
    GATE3_BLOCK_RMCB = "Gate3-Block/RMCB"


class StringType(StrEnum):
    DISCLAIMER = "DISCLAIMER"
    PI_LINK = "PI_LINK"
    CLAIM = "CLAIM"
    LEGAL_FOOTER = "LEGAL_FOOTER"
    ROUTING = "ROUTING"


class MutationOp(StrEnum):
    REPLACE_TEXT = "replace_text"
    ADD_REFERENCE = "add_reference"
    REMOVE_REFERENCE = "remove_reference"
    SET_FIELD = "set_field"
    ADD_CONDITION = "add_condition"
    REMOVE_CONDITION = "remove_condition"
    MODIFY_CONDITION = "modify_condition"
    ADD_ACTION = "add_action"
    REMOVE_ACTION = "remove_action"
    CHANGE_ROUTE = "change_route"
    ADD_FLAG = "add_flag"
    REMOVE_FLAG = "remove_flag"


class ValidationStatus(StrEnum):
    PASS = "PASS"
    WARN = "WARN"
    FAIL = "FAIL"


class RiskLevel(StrEnum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class ApprovalDecisionType(StrEnum):
    APPROVE = "APPROVE"
    APPROVE_AND_DEPLOY = "APPROVE_AND_DEPLOY"
    REQUEST_CHANGES = "REQUEST_CHANGES"
    REQUEST_CLARIFICATION = "REQUEST_CLARIFICATION"
    REJECT = "REJECT"


class ActorType(StrEnum):
    USER = "USER"
    SYSTEM = "SYSTEM"
    AI = "AI"
    WORKER = "WORKER"
    INTEGRATION = "INTEGRATION"


class SourceSystem(StrEnum):
    INTERNAL = "INTERNAL"
    WEBHOOK = "WEBHOOK"
    SERVICENOW = "SERVICENOW"
    JIRA = "JIRA"


class IntegrationStatus(StrEnum):
    ACTIVE = "ACTIVE"
    NOT_CONFIGURED = "NOT_CONFIGURED"
    ERROR = "ERROR"


class TestClassification(StrEnum):
    EXPECTED_CHANGE = "EXPECTED_CHANGE"
    UNCHANGED = "UNCHANGED"
    UNEXPECTED_CHANGE = "UNEXPECTED_CHANGE"
    FALSE_POSITIVE = "FALSE_POSITIVE"
    FALSE_NEGATIVE = "FALSE_NEGATIVE"


class CitationStatus(StrEnum):
    VERIFIED = "VERIFIED"
    UNVERIFIED = "UNVERIFIED"
    SYNTHETIC_DEMO = "SYNTHETIC_DEMO"
    CITATION_VERIFICATION_REQUIRED = "CITATION_VERIFICATION_REQUIRED"


class LogicOperator(StrEnum):
    EQ = "eq"
    NEQ = "neq"
    CONTAINS = "contains"
    NOT_CONTAINS = "not_contains"
    STARTS_WITH = "starts_with"
    ENDS_WITH = "ends_with"
    IN = "in"
    NOT_IN = "not_in"
    GT = "gt"
    GTE = "gte"
    LT = "lt"
    LTE = "lte"
    EXISTS = "exists"
    NOT_EXISTS = "not_exists"


class LogicCombinator(StrEnum):
    ALL = "all"
    ANY = "any"
    NOT = "not"


class LogicActionType(StrEnum):
    FLAG = "flag"
    ROUTE = "route"
    REQUIRE_DISCLAIMER = "require_disclaimer"
    REPLACE_TEXT = "replace_text"
    REQUIRE_REFERENCE = "require_reference"
    REJECT = "reject"
    WARN = "warn"
    REQUIRE_REVIEW = "require_review"


ALLOWED_TRANSITIONS: dict[WorkflowState, set[WorkflowState]] = {
    WorkflowState.RECEIVED: {WorkflowState.NORMALIZED, WorkflowState.NEEDS_CLARIFICATION},
    WorkflowState.NORMALIZED: {WorkflowState.INTERPRETING, WorkflowState.NEEDS_CLARIFICATION},
    WorkflowState.INTERPRETING: {
        WorkflowState.NEEDS_CLARIFICATION,
        WorkflowState.RULE_RESOLVING,
    },
    WorkflowState.NEEDS_CLARIFICATION: {WorkflowState.INTERPRETING, WorkflowState.CLOSED},
    WorkflowState.RULE_RESOLVING: {WorkflowState.RULE_RESOLVED, WorkflowState.NEEDS_CLARIFICATION},
    WorkflowState.RULE_RESOLVED: {WorkflowState.PROPOSING_CHANGE},
    WorkflowState.PROPOSING_CHANGE: {WorkflowState.PROPOSAL_READY},
    WorkflowState.PROPOSAL_READY: {WorkflowState.VALIDATING},
    WorkflowState.VALIDATING: {WorkflowState.VALIDATION_FAILED, WorkflowState.SANDBOXING},
    WorkflowState.VALIDATION_FAILED: {WorkflowState.PROPOSING_CHANGE, WorkflowState.CLOSED},
    WorkflowState.SANDBOXING: {WorkflowState.TESTING},
    WorkflowState.TESTING: {WorkflowState.REGRESSION_FAILED, WorkflowState.IMPACT_ANALYSIS},
    WorkflowState.REGRESSION_FAILED: {WorkflowState.PROPOSING_CHANGE, WorkflowState.CLOSED},
    WorkflowState.IMPACT_ANALYSIS: {WorkflowState.RISK_ASSESSMENT},
    WorkflowState.RISK_ASSESSMENT: {WorkflowState.AWAITING_APPROVAL},
    WorkflowState.AWAITING_APPROVAL: {
        WorkflowState.APPROVED,
        WorkflowState.REJECTED,
        WorkflowState.NEEDS_CLARIFICATION,
        WorkflowState.PROPOSING_CHANGE,
    },
    WorkflowState.APPROVED: {WorkflowState.DEPLOYING, WorkflowState.AWAITING_APPROVAL},
    WorkflowState.REJECTED: {WorkflowState.CLOSED, WorkflowState.PROPOSING_CHANGE},
    WorkflowState.DEPLOYING: {WorkflowState.DEPLOYED, WorkflowState.DEPLOYMENT_FAILED},
    WorkflowState.DEPLOYED: {WorkflowState.CLOSED, WorkflowState.ROLLED_BACK},
    WorkflowState.DEPLOYMENT_FAILED: {WorkflowState.AWAITING_APPROVAL, WorkflowState.CLOSED},
    WorkflowState.ROLLED_BACK: {WorkflowState.CLOSED, WorkflowState.AWAITING_APPROVAL},
    WorkflowState.CLOSED: set(),
}
