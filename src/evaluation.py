"""
Automated Evaluation Engine for AI Purchasing Agent.
Assesses decision correctness, information retrieval completeness,
constraint adherence, transactional action appropriateness,
and feedback loop validation integrity.
"""
from typing import List, Dict, Any
from src.erp_database import erp_db
from src.agents.buyer_orchestrator import buyer_orchestrator
from src.models import Scenario, DecisionReport


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
        criteria = [
            self.decision_correct,
            self.info_obtained,
            self.constraints_respected,
            self.action_appropriate,
            self.validated_feedback
        ]
        return round((sum(criteria) / len(criteria)) * 100, 1)

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
    """Run an isolated evaluation test on a specific scenario."""
    erp_db.reset()
    scenario = erp_db.scenarios.get(scenario_id)
    if not scenario:
        raise ValueError(f"Scenario {scenario_id} not found")

    report: DecisionReport = await buyer_orchestrator.run_purchasing_cycle(scenario)

    traces_by_agent = {t.agent_name: t for t in report.agent_traces}
    has_inv = "Inventory & Demand Specialist" in traces_by_agent
    has_sourcing = "Sourcing & Supplier Specialist" in traces_by_agent
    has_sentinel = "Constraint & Financial Sentinel" in traces_by_agent

    info_obtained = has_inv and has_sourcing and has_sentinel

    # Evaluate scenario specific correctness
    if scenario_id == "scenario_1":
        # Must MODIFY, quantity should not exceed 266 units (max storage 3.2 m3 / 0.012 m3 = 266 units)
        decision_correct = report.verdict == "MODIFY" and report.recommended_qty <= 266
        constraints_respected = report.recommended_qty * 0.012 <= 3.201
        action_appropriate = any(a["action"] == "CREATE_PURCHASE_ORDER" for a in report.actions_executed)
        validated_feedback = report.feedback_loop_passed

    elif scenario_id == "scenario_2":
        # Must SPLIT_SOURCING, cover the 250 unit shortfall with secondary supplier
        decision_correct = report.verdict == "SPLIT_SOURCING" and report.recommended_qty == 250
        constraints_respected = report.supplier_id == "supp_valle_verde_express"
        action_appropriate = (
            any(a["action"] == "MODIFY_EXISTING_PO" for a in report.actions_executed) and
            any(a["action"] == "CREATE_PURCHASE_ORDER" for a in report.actions_executed)
        )
        validated_feedback = report.feedback_loop_passed

    elif scenario_id == "scenario_3":
        # Must MODIFY to expand order due to surge
        decision_correct = report.verdict == "MODIFY" and report.recommended_qty > scenario.recommended_qty
        constraints_respected = True
        action_appropriate = any(a["action"] == "CREATE_PURCHASE_ORDER" for a in report.actions_executed)
        validated_feedback = report.feedback_loop_passed

    elif scenario_id == "scenario_4":
        # Must REJECT and escalate
        decision_correct = report.verdict == "REJECT" and report.recommended_qty == 0
        constraints_respected = report.human_approval_required is True
        action_appropriate = any(a["action"] == "HALT_PURCHASE_AND_ESCALATE" for a in report.actions_executed)
        validated_feedback = report.feedback_loop_passed

    else:
        decision_correct = False
        constraints_respected = False
        action_appropriate = False
        validated_feedback = False

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
    """Execute evaluation across all test scenarios."""
    results = []
    for sc_id in ["scenario_1", "scenario_2", "scenario_3", "scenario_4"]:
        res = await evaluate_scenario(sc_id)
        results.append(res.to_dict())

    avg_score = round(sum(r["score_percentage"] for r in results) / len(results), 1)
    all_passed = all(r["passed"] for r in results)

    return {
        "overall_evaluation_score": avg_score,
        "overall_status": "PASSED" if all_passed else "NEEDS_ATTENTION",
        "total_scenarios_evaluated": len(results),
        "results": results
    }
