"""Pure Goal Discovery and initial approval semantics for Generic ADG."""

from __future__ import annotations

from dataclasses import dataclass, replace
from enum import Enum
from typing import Any, Mapping, Sequence


class GoalDiscoveryValidationError(ValueError):
    """Raised when Goal Discovery state or a transition violates the Core contract."""


class BootstrapPhase(str, Enum):
    SEED_GOAL = "SEED_GOAL"
    GOAL_DISCOVERY = "GOAL_DISCOVERY"
    PLAN_DRAFTED = "PLAN_DRAFTED"
    WAITING_GOAL_APPROVAL = "WAITING_GOAL_APPROVAL"
    APPROVED = "APPROVED"


class GoalTopic(str, Enum):
    DESIRED_OUTCOME = "DESIRED_OUTCOME"
    PROBLEM_OR_MOTIVATION = "PROBLEM_OR_MOTIVATION"
    INTENDED_USER_OR_BENEFICIARY = "INTENDED_USER_OR_BENEFICIARY"
    COMPLETION_CRITERIA = "COMPLETION_CRITERIA"
    CONSTRAINTS = "CONSTRAINTS"
    NON_GOALS = "NON_GOALS"
    HUMAN_DECISION_BOUNDARIES = "HUMAN_DECISION_BOUNDARIES"


class TopicStatus(str, Enum):
    UNRESOLVED = "UNRESOLVED"
    RESOLVED = "RESOLVED"
    NOT_APPLICABLE = "NOT_APPLICABLE"


class HumanApprovalAction(str, Enum):
    APPROVE = "APPROVE"
    REQUEST_CHANGES = "REQUEST_CHANGES"


_REQUIRED_KNOWN_TOPICS = {
    GoalTopic.DESIRED_OUTCOME,
    GoalTopic.COMPLETION_CRITERIA,
}


@dataclass(frozen=True, slots=True)
class GoalTopicState:
    topic: GoalTopic
    status: TopicStatus = TopicStatus.UNRESOLVED
    summary: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.topic, GoalTopic):
            raise GoalDiscoveryValidationError("topic must be a supported GoalTopic")
        if not isinstance(self.status, TopicStatus):
            raise GoalDiscoveryValidationError("status must be a supported TopicStatus")

        if self.status is TopicStatus.UNRESOLVED:
            if self.summary is not None:
                raise GoalDiscoveryValidationError(
                    "UNRESOLVED goal topic must not include summary"
                )
            return

        _require_non_empty_string("summary", self.summary)
        if (
            self.topic in _REQUIRED_KNOWN_TOPICS
            and self.status is TopicStatus.NOT_APPLICABLE
        ):
            raise GoalDiscoveryValidationError(
                f"{self.topic.value} cannot be NOT_APPLICABLE"
            )

    @classmethod
    def from_mapping(cls, raw: Mapping[str, Any]) -> "GoalTopicState":
        _require_mapping("goal topic state", raw)
        _reject_unknown(raw, {"topic", "status", "summary"}, "goal topic state")
        _require_fields(raw, ("topic", "status"), "goal topic state")
        try:
            topic = GoalTopic(raw["topic"])
            status = TopicStatus(raw["status"])
        except (TypeError, ValueError) as exc:
            raise GoalDiscoveryValidationError("unsupported goal topic/status") from exc
        return cls(topic=topic, status=status, summary=raw.get("summary"))

    def to_mapping(self) -> dict[str, Any]:
        return {
            "topic": self.topic.value,
            "status": self.status.value,
            "summary": self.summary,
        }


@dataclass(frozen=True, slots=True)
class GoalDiscoverySnapshot:
    topics: tuple[GoalTopicState, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.topics, tuple):
            raise GoalDiscoveryValidationError("topics must be stored as a tuple")
        if not all(isinstance(item, GoalTopicState) for item in self.topics):
            raise GoalDiscoveryValidationError(
                "topics must contain only validated GoalTopicState values"
            )
        seen = [item.topic for item in self.topics]
        if len(set(seen)) != len(seen):
            raise GoalDiscoveryValidationError("goal topics must not contain duplicates")
        missing = [topic.value for topic in GoalTopic if topic not in set(seen)]
        if missing:
            raise GoalDiscoveryValidationError(
                f"missing goal topics: {', '.join(missing)}"
            )
        if len(seen) != len(GoalTopic):
            raise GoalDiscoveryValidationError(
                "goal topics must contain each topic once"
            )

    @classmethod
    def unresolved(cls) -> "GoalDiscoverySnapshot":
        return cls(tuple(GoalTopicState(topic) for topic in GoalTopic))

    @property
    def is_sufficient(self) -> bool:
        return all(item.status is not TopicStatus.UNRESOLVED for item in self.topics)

    @property
    def unresolved_topics(self) -> tuple[GoalTopic, ...]:
        return tuple(
            item.topic
            for item in self.topics
            if item.status is TopicStatus.UNRESOLVED
        )

    def with_topic(
        self,
        topic: GoalTopic,
        status: TopicStatus,
        summary: str | None = None,
    ) -> "GoalDiscoverySnapshot":
        if not isinstance(topic, GoalTopic):
            raise GoalDiscoveryValidationError("topic must be a supported GoalTopic")
        replacement = GoalTopicState(topic=topic, status=status, summary=summary)
        return GoalDiscoverySnapshot(
            tuple(replacement if item.topic is topic else item for item in self.topics)
        )

    @classmethod
    def from_mapping(cls, raw: Mapping[str, Any]) -> "GoalDiscoverySnapshot":
        _require_mapping("goal discovery snapshot", raw)
        _reject_unknown(raw, {"topics"}, "goal discovery snapshot")
        _require_fields(raw, ("topics",), "goal discovery snapshot")
        topics_raw = raw["topics"]
        if isinstance(topics_raw, (str, bytes)) or not isinstance(
            topics_raw, Sequence
        ):
            raise GoalDiscoveryValidationError("topics must be a list")
        return cls(tuple(GoalTopicState.from_mapping(item) for item in topics_raw))

    def to_mapping(self) -> dict[str, Any]:
        return {"topics": [item.to_mapping() for item in self.topics]}


@dataclass(frozen=True, slots=True)
class ProjectPlanDraft:
    proposed_project_name: str
    project_goal: str
    completion_criteria: tuple[str, ...]
    roadmap_summary: str
    first_bounded_work: str
    constraints: tuple[str, ...] = ()
    non_goals: tuple[str, ...] = ()
    required_resources: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        _require_non_empty_string("proposed_project_name", self.proposed_project_name)
        _require_non_empty_string("project_goal", self.project_goal)
        _validate_string_tuple(
            "completion_criteria", self.completion_criteria, require_non_empty=True
        )
        _require_non_empty_string("roadmap_summary", self.roadmap_summary)
        _require_non_empty_string("first_bounded_work", self.first_bounded_work)
        _validate_string_tuple("constraints", self.constraints)
        _validate_string_tuple("non_goals", self.non_goals)
        _validate_string_tuple("required_resources", self.required_resources)

    @classmethod
    def from_mapping(cls, raw: Mapping[str, Any]) -> "ProjectPlanDraft":
        _require_mapping("project plan draft", raw)
        allowed = {
            "proposed_project_name",
            "project_goal",
            "completion_criteria",
            "roadmap_summary",
            "first_bounded_work",
            "constraints",
            "non_goals",
            "required_resources",
        }
        _reject_unknown(raw, allowed, "project plan draft")
        _require_fields(
            raw,
            (
                "proposed_project_name",
                "project_goal",
                "completion_criteria",
                "roadmap_summary",
                "first_bounded_work",
            ),
            "project plan draft",
        )
        return cls(
            proposed_project_name=raw["proposed_project_name"],
            project_goal=raw["project_goal"],
            completion_criteria=_coerce_string_tuple(
                "completion_criteria",
                raw["completion_criteria"],
                require_non_empty=True,
            ),
            roadmap_summary=raw["roadmap_summary"],
            first_bounded_work=raw["first_bounded_work"],
            constraints=_coerce_string_tuple("constraints", raw.get("constraints", ())),
            non_goals=_coerce_string_tuple("non_goals", raw.get("non_goals", ())),
            required_resources=_coerce_string_tuple(
                "required_resources", raw.get("required_resources", ())
            ),
        )

    def to_mapping(self) -> dict[str, Any]:
        return {
            "proposed_project_name": self.proposed_project_name,
            "project_goal": self.project_goal,
            "completion_criteria": list(self.completion_criteria),
            "roadmap_summary": self.roadmap_summary,
            "first_bounded_work": self.first_bounded_work,
            "constraints": list(self.constraints),
            "non_goals": list(self.non_goals),
            "required_resources": list(self.required_resources),
        }


@dataclass(frozen=True, slots=True)
class BootstrapState:
    phase: BootstrapPhase
    seed_goal: str | None = None
    discovery: GoalDiscoverySnapshot | None = None
    plan_draft: ProjectPlanDraft | None = None
    change_request: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.phase, BootstrapPhase):
            raise GoalDiscoveryValidationError(
                "phase must be a supported BootstrapPhase"
            )
        _require_optional_type("discovery", self.discovery, GoalDiscoverySnapshot)
        _require_optional_type("plan_draft", self.plan_draft, ProjectPlanDraft)
        if self.change_request is not None:
            _require_non_empty_string("change_request", self.change_request)

        if self.phase is BootstrapPhase.SEED_GOAL:
            if any(
                value is not None
                for value in (
                    self.seed_goal,
                    self.discovery,
                    self.plan_draft,
                    self.change_request,
                )
            ):
                raise GoalDiscoveryValidationError(
                    "SEED_GOAL must not contain project-specific bootstrap data"
                )
            return

        _require_non_empty_string("seed_goal", self.seed_goal)
        if self.discovery is None:
            raise GoalDiscoveryValidationError(
                f"{self.phase.value} requires goal discovery state"
            )

        if self.phase is BootstrapPhase.GOAL_DISCOVERY:
            if self.plan_draft is not None:
                raise GoalDiscoveryValidationError(
                    "GOAL_DISCOVERY must not contain a plan draft"
                )
            return

        if not self.discovery.is_sufficient:
            raise GoalDiscoveryValidationError(
                f"{self.phase.value} requires sufficient goal discovery"
            )
        if self.plan_draft is None:
            raise GoalDiscoveryValidationError(
                f"{self.phase.value} requires a project plan draft"
            )
        if self.change_request is not None:
            raise GoalDiscoveryValidationError(
                f"{self.phase.value} must not contain change_request"
            )

    @classmethod
    def from_mapping(cls, raw: Mapping[str, Any]) -> "BootstrapState":
        _require_mapping("bootstrap state", raw)
        allowed = {
            "phase",
            "seed_goal",
            "discovery",
            "plan_draft",
            "change_request",
        }
        _reject_unknown(raw, allowed, "bootstrap state")
        _require_fields(raw, ("phase",), "bootstrap state")
        try:
            phase = BootstrapPhase(raw["phase"])
        except (TypeError, ValueError) as exc:
            raise GoalDiscoveryValidationError(
                f"unsupported bootstrap phase: {raw['phase']!r}"
            ) from exc
        return cls(
            phase=phase,
            seed_goal=raw.get("seed_goal"),
            discovery=_parse_optional_mapping(
                "discovery",
                raw.get("discovery"),
                GoalDiscoverySnapshot.from_mapping,
            ),
            plan_draft=_parse_optional_mapping(
                "plan_draft",
                raw.get("plan_draft"),
                ProjectPlanDraft.from_mapping,
            ),
            change_request=raw.get("change_request"),
        )

    def to_mapping(self) -> dict[str, Any]:
        return {
            "phase": self.phase.value,
            "seed_goal": self.seed_goal,
            "discovery": self.discovery.to_mapping() if self.discovery else None,
            "plan_draft": self.plan_draft.to_mapping() if self.plan_draft else None,
            "change_request": self.change_request,
        }


def new_bootstrap_state() -> BootstrapState:
    return BootstrapState(BootstrapPhase.SEED_GOAL)


def begin_goal_discovery(state: BootstrapState, seed_goal: str) -> BootstrapState:
    _require_state_phase(state, BootstrapPhase.SEED_GOAL)
    _require_non_empty_string("seed_goal", seed_goal)
    return BootstrapState(
        phase=BootstrapPhase.GOAL_DISCOVERY,
        seed_goal=seed_goal,
        discovery=GoalDiscoverySnapshot.unresolved(),
    )


def record_goal_topic(
    state: BootstrapState,
    topic: GoalTopic,
    status: TopicStatus,
    summary: str | None = None,
) -> BootstrapState:
    _require_state_phase(state, BootstrapPhase.GOAL_DISCOVERY)
    assert state.discovery is not None
    return replace(
        state,
        discovery=state.discovery.with_topic(topic, status, summary),
    )


def draft_project_plan(
    state: BootstrapState,
    plan_draft: ProjectPlanDraft,
) -> BootstrapState:
    _require_state_phase(state, BootstrapPhase.GOAL_DISCOVERY)
    if not isinstance(plan_draft, ProjectPlanDraft):
        raise GoalDiscoveryValidationError(
            "plan_draft must be a validated ProjectPlanDraft"
        )
    assert state.discovery is not None
    if not state.discovery.is_sufficient:
        missing = ", ".join(topic.value for topic in state.discovery.unresolved_topics)
        raise GoalDiscoveryValidationError(
            f"goal discovery is not sufficient; unresolved: {missing}"
        )
    return BootstrapState(
        phase=BootstrapPhase.PLAN_DRAFTED,
        seed_goal=state.seed_goal,
        discovery=state.discovery,
        plan_draft=plan_draft,
    )


def request_goal_approval(state: BootstrapState) -> BootstrapState:
    _require_state_phase(state, BootstrapPhase.PLAN_DRAFTED)
    return replace(state, phase=BootstrapPhase.WAITING_GOAL_APPROVAL)


def resolve_goal_approval(
    state: BootstrapState,
    action: HumanApprovalAction,
    reason: str,
) -> BootstrapState:
    _require_state_phase(state, BootstrapPhase.WAITING_GOAL_APPROVAL)
    if not isinstance(action, HumanApprovalAction):
        raise GoalDiscoveryValidationError(
            "action must be a supported HumanApprovalAction"
        )
    _require_non_empty_string("reason", reason)

    if action is HumanApprovalAction.APPROVE:
        return replace(state, phase=BootstrapPhase.APPROVED)

    return BootstrapState(
        phase=BootstrapPhase.GOAL_DISCOVERY,
        seed_goal=state.seed_goal,
        discovery=state.discovery,
        change_request=reason,
    )


def _require_state_phase(state: Any, expected: BootstrapPhase) -> None:
    if not isinstance(state, BootstrapState):
        raise GoalDiscoveryValidationError(
            "state must be a validated BootstrapState"
        )
    if state.phase is not expected:
        raise GoalDiscoveryValidationError(
            f"expected phase {expected.value}, got {state.phase.value}"
        )


def _require_non_empty_string(field: str, value: Any) -> None:
    if not isinstance(value, str) or not value.strip():
        raise GoalDiscoveryValidationError(f"{field} must be a non-empty string")


def _require_optional_type(field: str, value: Any, expected: type[Any]) -> None:
    if value is not None and not isinstance(value, expected):
        raise GoalDiscoveryValidationError(
            f"{field} must be validated {expected.__name__} or None"
        )


def _validate_string_tuple(
    field: str,
    values: tuple[str, ...],
    *,
    require_non_empty: bool = False,
) -> None:
    if not isinstance(values, tuple):
        raise GoalDiscoveryValidationError(f"{field} must be stored as a tuple")
    if require_non_empty and not values:
        raise GoalDiscoveryValidationError(f"{field} must not be empty")
    for index, value in enumerate(values):
        if not isinstance(value, str) or not value.strip():
            raise GoalDiscoveryValidationError(
                f"{field}[{index}] must be a non-empty string"
            )


def _coerce_string_tuple(
    field: str,
    value: Any,
    *,
    require_non_empty: bool = False,
) -> tuple[str, ...]:
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence):
        raise GoalDiscoveryValidationError(f"{field} must be a list of strings")
    result = tuple(value)
    _validate_string_tuple(field, result, require_non_empty=require_non_empty)
    return result


def _require_mapping(label: str, raw: Any) -> None:
    if not isinstance(raw, Mapping):
        raise GoalDiscoveryValidationError(f"{label} must be a mapping")


def _reject_unknown(raw: Mapping[str, Any], allowed: set[str], label: str) -> None:
    unknown = sorted(set(raw) - allowed)
    if unknown:
        raise GoalDiscoveryValidationError(
            f"unknown {label} fields: {', '.join(unknown)}"
        )


def _require_fields(
    raw: Mapping[str, Any],
    required: tuple[str, ...],
    label: str,
) -> None:
    missing = [field for field in required if field not in raw]
    if missing:
        raise GoalDiscoveryValidationError(
            f"missing required {label} fields: {', '.join(missing)}"
        )


def _parse_optional_mapping(field: str, raw: Any, parser: Any) -> Any:
    if raw is None:
        return None
    if not isinstance(raw, Mapping):
        raise GoalDiscoveryValidationError(f"{field} must be a mapping or None")
    return parser(raw)
