from enum import StrEnum


class Action(StrEnum):
    READ_DOCUMENTATION = "read_documentation"
    READ_DEVELOPMENT = "read_development"
    CREATE_CAMPAIGN = "create_campaign"
    PROPOSE_HYPOTHESIS = "propose_hypothesis"
    APPROVE_HYPOTHESIS = "approve_hypothesis"
    REJECT_HYPOTHESIS = "reject_hypothesis"
    REJECT_CAMPAIGN = "reject_campaign"
    CREATE_SPEC = "create_spec"
    REGISTER_EXPERIMENT = "register_experiment"
    RECORD_OUTCOME = "record_outcome"
    RECORD_CORRECTION = "record_correction"
    INVALIDATE = "invalidate"
    MODIFY_LOCKED_CONFIG = "modify_locked_config"
    MODIFY_PROTECTED_LOGIC = "modify_protected_logic"
    MODIFY_HISTORY = "modify_history"
    ADD_PRIMITIVE = "add_primitive"
    FINAL_EVALUATION = "final_evaluation"
    PUBLISH_CLAIM = "publish_claim"


class Outcome(StrEnum):
    ALLOW = "ALLOW"
    DENY = "DENY"
    REQUIRE_APPROVAL = "REQUIRE_APPROVAL"
