"""
Test Suite for AI Purchasing Agent Scenarios and Feedback Loops.
Validates business logic, constraint compliance, and agent decisions.
"""
import pytest
from src.erp_database import erp_db
from src.agents.buyer_orchestrator import buyer_orchestrator
from src.evaluation import evaluate_scenario, run_full_evaluation
from src.erp_tools import validate_purchase_order_constraints


@pytest.fixture(autouse=True)
def reset_database():
    """Reset mock ERP database before each test run."""
    erp_db.reset()
    yield


@pytest.mark.asyncio
async def test_scenario_1_storage_constraint_remediation():
    """
    Scenario 1: System recommends 800 units, but CDMX node only has 3.2 m3 available.
    Agent must NOT blindly accept. It must modify quantity down to 260 units
    (fitting in 3.12 m3 and satisfying MOQ 250).
    """
    eval_res = await evaluate_scenario("scenario_1")
    assert eval_res.score_percentage == 100.0
    assert eval_res.decision_correct is True
    assert eval_res.constraints_respected is True
    assert eval_res.action_appropriate is True
    assert eval_res.validated_feedback is True

    # Assert ERP state was actually updated
    node = erp_db.get_node("node_cdmx_roma")
    assert node.available_storage_m3 >= 0.0, "Storage should not be in negative overflow"
    assert node.available_budget >= 0.0, "Budget should not be overspent"


@pytest.mark.asyncio
async def test_scenario_2_supplier_shortfall_recovery():
    """
    Scenario 2: Supplier Agrícola Central only fulfills 250 of 500 units.
    Agent must update original PO to 250 and issue emergency split PO to Valle Verde Express.
    """
    eval_res = await evaluate_scenario("scenario_2")
    assert eval_res.score_percentage == 100.0
    assert eval_res.decision_correct is True
    assert eval_res.action_appropriate is True

    # Verify original PO status in ERP
    original_po = erp_db.purchase_orders["po_scenario_2"]
    assert original_po.confirmed_qty == 250
    assert original_po.status == "PARTIALLY_FULFILLED"


@pytest.mark.asyncio
async def test_scenario_3_demand_surge_expansion():
    """
    Scenario 3: Demand surge (+80%) requires expanding PO to prevent 48h stockout.
    """
    eval_res = await evaluate_scenario("scenario_3")
    assert eval_res.score_percentage == 100.0
    assert eval_res.decision_correct is True
    assert eval_res.validated_feedback is True


@pytest.mark.asyncio
async def test_scenario_4_hard_constraint_human_escalation():
    """
    Scenario 4: Storage saturated (95% full) and budget crunch in São Paulo.
    Agent must safely REJECT the purchase and escalate to human category lead.
    """
    eval_res = await evaluate_scenario("scenario_4")
    assert eval_res.score_percentage == 100.0
    assert eval_res.decision_correct is True
    assert eval_res.constraints_respected is True

    # Check that no invalid PO was created
    sp_pos = erp_db.get_open_pos(node_id="node_sao_paulo_pinheiros")
    assert len(sp_pos) == 0, "No PO should be created for rejected scenario"


def test_deterministic_constraint_sentinel_blocks_overflow():
    """
    Directly test the Deterministic Constraint Sentinel guardrail.
    Ensure that attempting to force 800 units fails with an actionable remediation.
    """
    val = validate_purchase_order_constraints(
        product_id="prod_oat_milk_barista",
        node_id="node_cdmx_roma",
        supplier_id="supp_oat_master",
        quantity=800
    )
    assert val.is_valid is False
    assert val.storage_ok is False
    assert "exceeds available storage" in val.violations[0]
    assert val.remediation_suggestion is not None
    assert "Adjust order quantity" in val.remediation_suggestion


@pytest.mark.asyncio
async def test_full_evaluation_suite():
    """
    Run the overall evaluation benchmark across all test scenarios.
    """
    full_eval = await run_full_evaluation()
    assert full_eval["overall_status"] == "PASSED"
    assert full_eval["overall_evaluation_score"] == 100.0
    assert full_eval["total_scenarios_evaluated"] == 4
