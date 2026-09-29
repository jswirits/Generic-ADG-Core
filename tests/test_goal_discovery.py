from __future__ import annotations

import unittest
from dataclasses import FrozenInstanceError

from generic_adg_core import (
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


def sample_plan() -> ProjectPlanDraft:
    return ProjectPlanDraft(
        proposed_project_name="Example Project",
        project_goal="Deliver the approved outcome.",
        completion_criteria=("The approved outcome is demonstrated.",),
        roadmap_summary="Discover, approve, then implement bounded work.",
        first_bounded_work="Create the smallest verified artifact.",
        constraints=("Remain inside the approved boundary.",),
        non_goals=("Unapproved integrations",),
        required_resources=("Python 3.12",),
    )


def sufficient_discovery_state() -> BootstrapState:
    state = begin_goal_discovery(new_bootstrap_state(), "Build a useful project")
    for topic in GoalTopic:
        state = record_goal_topic(
            state,
            topic,
            TopicStatus.RESOLVED,
            f"Resolved {topic.value.lower()}",
        )
    return state


def waiting_approval_state() -> BootstrapState:
    drafted = draft_project_plan(sufficient_discovery_state(), sample_plan())
    return request_goal_approval(drafted)


class GoalDiscoveryTests(unittest.TestCase):
    def test_complete_approval_path(self) -> None:
        seed = new_bootstrap_state()
        self.assertEqual(seed.phase, BootstrapPhase.SEED_GOAL)

        discovering = sufficient_discovery_state()
        self.assertTrue(discovering.discovery.is_sufficient)

        drafted = draft_project_plan(discovering, sample_plan())
        self.assertEqual(drafted.phase, BootstrapPhase.PLAN_DRAFTED)

        waiting = request_goal_approval(drafted)
        self.assertEqual(waiting.phase, BootstrapPhase.WAITING_GOAL_APPROVAL)

        approved = resolve_goal_approval(
            waiting,
            HumanApprovalAction.APPROVE,
            "The goal and plan are correct.",
        )
        self.assertEqual(approved.phase, BootstrapPhase.APPROVED)
        self.assertIsNone(approved.change_request)

    def test_change_request_returns_to_discovery_and_is_cleared_by_redraft(self) -> None:
        changed = resolve_goal_approval(
            waiting_approval_state(),
            HumanApprovalAction.REQUEST_CHANGES,
            "Clarify the completion evidence.",
        )
        self.assertEqual(changed.phase, BootstrapPhase.GOAL_DISCOVERY)
        self.assertEqual(changed.change_request, "Clarify the completion evidence.")

        redrafted = draft_project_plan(changed, sample_plan())
        self.assertEqual(redrafted.phase, BootstrapPhase.PLAN_DRAFTED)
        self.assertIsNone(redrafted.change_request)

    def test_serialization_round_trip(self) -> None:
        approved = resolve_goal_approval(
            waiting_approval_state(),
            HumanApprovalAction.APPROVE,
            "Approved.",
        )
        self.assertEqual(
            BootstrapState.from_mapping(approved.to_mapping()),
            approved,
        )

    def test_unknown_fields_fail_closed_at_each_mapping_level(self) -> None:
        valid = waiting_approval_state().to_mapping()
        for path in ("state", "discovery", "topic", "plan"):
            raw = waiting_approval_state().to_mapping()
            if path == "state":
                raw["unexpected"] = True
            elif path == "discovery":
                raw["discovery"]["unexpected"] = True
            elif path == "topic":
                raw["discovery"]["topics"][0]["unexpected"] = True
            else:
                raw["plan_draft"]["unexpected"] = True
            with self.subTest(path=path):
                with self.assertRaises(GoalDiscoveryValidationError):
                    BootstrapState.from_mapping(raw)
        self.assertEqual(BootstrapState.from_mapping(valid).to_mapping(), valid)

    def test_incomplete_discovery_cannot_be_drafted(self) -> None:
        state = begin_goal_discovery(new_bootstrap_state(), "Build a useful project")
        with self.assertRaisesRegex(
            GoalDiscoveryValidationError,
            "goal discovery is not sufficient",
        ):
            draft_project_plan(state, sample_plan())

    def test_all_topics_are_present_once_in_new_discovery(self) -> None:
        state = begin_goal_discovery(new_bootstrap_state(), "Build a useful project")
        topics = tuple(item.topic for item in state.discovery.topics)
        self.assertEqual(topics, tuple(GoalTopic))
        self.assertEqual(len(set(topics)), len(GoalTopic))

    def test_missing_and_duplicate_topics_are_rejected(self) -> None:
        topics = GoalDiscoverySnapshot.unresolved().topics
        with self.assertRaisesRegex(GoalDiscoveryValidationError, "missing goal topics"):
            GoalDiscoverySnapshot(topics[:-1])
        with self.assertRaisesRegex(GoalDiscoveryValidationError, "duplicates"):
            GoalDiscoverySnapshot(topics + (topics[0],))

    def test_required_topics_cannot_be_not_applicable(self) -> None:
        for topic in (GoalTopic.DESIRED_OUTCOME, GoalTopic.COMPLETION_CRITERIA):
            with self.subTest(topic=topic):
                with self.assertRaisesRegex(
                    GoalDiscoveryValidationError,
                    "cannot be NOT_APPLICABLE",
                ):
                    GoalTopicState(topic, TopicStatus.NOT_APPLICABLE, "Not needed")

    def test_optional_topic_can_be_not_applicable(self) -> None:
        value = GoalTopicState(
            GoalTopic.NON_GOALS,
            TopicStatus.NOT_APPLICABLE,
            "No non-goals were identified.",
        )
        self.assertEqual(value.status, TopicStatus.NOT_APPLICABLE)

    def test_seed_goal_must_be_non_empty(self) -> None:
        for value in ("", "   ", None):
            with self.subTest(value=value):
                with self.assertRaises(GoalDiscoveryValidationError):
                    begin_goal_discovery(new_bootstrap_state(), value)

    def test_invalid_phase_transition_is_rejected(self) -> None:
        with self.assertRaisesRegex(
            GoalDiscoveryValidationError,
            "expected phase PLAN_DRAFTED",
        ):
            request_goal_approval(new_bootstrap_state())

    def test_approval_requires_typed_action_and_reason(self) -> None:
        waiting = waiting_approval_state()
        with self.assertRaisesRegex(GoalDiscoveryValidationError, "supported"):
            resolve_goal_approval(waiting, "APPROVE", "Approved.")
        with self.assertRaisesRegex(GoalDiscoveryValidationError, "non-empty"):
            resolve_goal_approval(waiting, HumanApprovalAction.APPROVE, " ")

    def test_plan_fields_are_strict_and_completion_criteria_are_required(self) -> None:
        raw = sample_plan().to_mapping()
        raw["completion_criteria"] = []
        with self.assertRaisesRegex(GoalDiscoveryValidationError, "must not be empty"):
            ProjectPlanDraft.from_mapping(raw)

        raw = sample_plan().to_mapping()
        raw["completion_criteria"] = "not a list"
        with self.assertRaisesRegex(GoalDiscoveryValidationError, "list of strings"):
            ProjectPlanDraft.from_mapping(raw)

    def test_values_are_immutable(self) -> None:
        state = sufficient_discovery_state()
        with self.assertRaises(FrozenInstanceError):
            state.seed_goal = "changed"
        with self.assertRaises(TypeError):
            state.discovery.topics[0] = GoalTopicState(GoalTopic.DESIRED_OUTCOME)

    def test_constructed_state_must_match_phase_invariants(self) -> None:
        discovery = GoalDiscoverySnapshot.unresolved()
        with self.assertRaisesRegex(
            GoalDiscoveryValidationError,
            "SEED_GOAL must not contain",
        ):
            BootstrapState(BootstrapPhase.SEED_GOAL, seed_goal="Unexpected")
        with self.assertRaisesRegex(
            GoalDiscoveryValidationError,
            "requires sufficient goal discovery",
        ):
            BootstrapState(
                BootstrapPhase.PLAN_DRAFTED,
                seed_goal="Goal",
                discovery=discovery,
                plan_draft=sample_plan(),
            )


if __name__ == "__main__":
    unittest.main()
