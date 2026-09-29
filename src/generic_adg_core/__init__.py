"""Public surface for the Generic ADG Core baseline."""

from .goal_discovery import (
    BootstrapPhase,
    BootstrapState,
    GoalDiscoverySnapshot,
    GoalDiscoveryValidationError,
    GoalTopic,
    GoalTopicState,
    HumanApprovalAction,
    ProjectPlanDraft,
    TopicStatus,
    begin_goal_discovery,
    draft_project_plan,
    new_bootstrap_state,
    record_goal_topic,
    request_goal_approval,
    resolve_goal_approval,
)

__version__ = "0.1.0"

__all__ = [
    "BootstrapPhase",
    "BootstrapState",
    "GoalDiscoverySnapshot",
    "GoalDiscoveryValidationError",
    "GoalTopic",
    "GoalTopicState",
    "HumanApprovalAction",
    "ProjectPlanDraft",
    "TopicStatus",
    "begin_goal_discovery",
    "draft_project_plan",
    "new_bootstrap_state",
    "record_goal_topic",
    "request_goal_approval",
    "resolve_goal_approval",
]
