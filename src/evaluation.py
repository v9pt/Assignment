"""
Evaluation harness.

Runs each scenario through the purchasing agent and checks the outcome
against a set of correctness criteria aligned with the assignment rubric:
  - Was the decision correct?
  - Did the agent obtain the necessary information?
  - Did it respect constraints?
  - Did it take the right action?
  - Did it validate the result?
"""
from typing import Dict, Any
from src.erp_database import erp_db
from src.agents.buyer_orchestrator import buyer_orchestrator
from src.models import DecisionReport


class EvaluationResult:
    def __init__(
        self,
        scenario_id: str,
        scenario_name: str,
        decision_correct: bool,
        info_obtained: bool,
        constraints_respected: bool,
        action_appropriate: bool,
        validated_feedback: bool,
        details: Dict[str, Any]
    ):
        self.scenario_id = scenario_id
        self.scenario_name = scenario_name
        self.decision_correct = decision_correct
        self.info_obtained = info_obtained
        self.constraints_respected = constraints_respected
        self.action_appropriate = action_appropriate
        self.validated_feedback = validated_feedback
        self.details = details

    @property
    def score_percentage(self) -> float:
        checks = [
            self.decision_correct,
            self.info_obtained,
            self.constraints_respected,
            self.action_appropriate,
            self.validated_feedback
        ]
        return round(sum(checks) / len(checks) * 100, 1)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "scenario_id": self.scenario_id,
            "scenario_name": self.scenario_name,
            "score_percentage": self.score_percentage,
            "passed": self.score_percentage >= 80.0,
            "checklist": {
                "decision_correct": self.decision_correct,
                "information_retrieved": self.info_obtained,
                "constraints_respected": self.constraints_respected,
                "action_appropriate": self.action_appropriate,
                "feedback_loop_validated": self.validated_feedback
            },
            "details": self.details
        }


async def evaluate_scenario(scenario_id: str) -> EvaluationResult:
    """Run one scenario in isolation and grade the agent's decision."""
    erp_db.reset()
    scenario = erp_db.scenarios.get(scenario_id)
    if not scenario:
        raise ValueError(f"Unknown scenario: {scenario_id}")

    report: DecisionReport = await buyer_orchestrator.run_purchasing_cycle(scenario)

    # Check that all three specialist agents ran
    agent_names = {t.agent_name for t in report.agent_traces}
    info_obtained = (
        "Inventory & Demand Analyst" in agent_names
        and "Sourcing Specialist" in agent_names
        and "Constraint Validator" in agent_names
    )

    if scenario_id == "scenario_1":
        # Should MODIFY to ≤266 units (3.2 m3 / 0.012 m3 per unit)
        decision_correct = report.verdict == "MODIFY" and report.recommended_qty <= 266
        constraints_respected = report.recommended_qty * 0.012 <= 3.201
        action_appropriate = any(a["action"] == "CREATE_PURCHASE_ORDER" for a in report.actions_executed)
        validated_feedback = report.feedback_loop_passed

    elif scenario_id == "scenario_2":
        # Should split-source: update original PO + create recovery order
        decision_correct = report.verdict == "SPLIT_SOURCING" and report.recommended_qty == 250
        constraints_respected = report.supplier_id == "supp_valle_verde_express"
        action_appropriate = (
            any(a["action"] == "MODIFY_EXISTING_PO" for a in report.actions_executed)
            and any(a["action"] == "CREATE_PURCHASE_ORDER" for a in report.actions_executed)
        )
        validated_feedback = report.feedback_loop_passed

    elif scenario_id == "scenario_3":
        # Should expand the order beyond the original recommendation
        decision_correct = report.verdict == "MODIFY" and report.recommended_qty > scenario.recommended_qty
        constraints_respected = True
        action_appropriate = any(a["action"] == "CREATE_PURCHASE_ORDER" for a in report.actions_executed)
        validated_feedback = report.feedback_loop_passed

    elif scenario_id == "scenario_4":
        # Should reject and escalate
        decision_correct = report.verdict == "REJECT" and report.recommended_qty == 0
        constraints_respected = report.human_approval_required is True
        action_appropriate = any(a["action"] == "ESCALATE_TO_HUMAN" for a in report.actions_executed)
        validated_feedback = report.feedback_loop_passed

    else:
        decision_correct = constraints_respected = action_appropriate = validated_feedback = False

    return EvaluationResult(
        scenario_id=scenario.id,
        scenario_name=scenario.title,
        decision_correct=decision_correct,
        info_obtained=info_obtained,
        constraints_respected=constraints_respected,
        action_appropriate=action_appropriate,
        validated_feedback=validated_feedback,
        details={
            "verdict": report.verdict,
            "recommended_qty": report.recommended_qty,
            "feedback_loop_details": report.feedback_loop_details,
            "rationale": report.rationale
        }
    )


async def run_full_evaluation() -> Dict[str, Any]:
    results = []
    for sc_id in ["scenario_1", "scenario_2", "scenario_3", "scenario_4"]:
        r = await evaluate_scenario(sc_id)
        results.append(r.to_dict())

    avg = round(sum(r["score_percentage"] for r in results) / len(results), 1)
    return {
        "overall_evaluation_score": avg,
        "overall_status": "PASSED" if all(r["passed"] for r in results) else "NEEDS_ATTENTION",
        "total_scenarios_evaluated": len(results),
        "results": results
    }
