import pytest
from src.erp_database import erp_db
from src.agents.buyer_orchestrator import buyer_orchestrator
from src.evaluation import evaluate_scenario, run_full_evaluation
from src.erp_tools import validate_purchase_order_constraints


@pytest.fixture(autouse=True)
def reset_database():
    erp_db.reset()
    yield


@pytest.mark.asyncio
async def test_scenario_1_modify_for_storage():
    """800-unit recommendation should be downsized to fit 3.2 m3 storage."""
    res = await evaluate_scenario("scenario_1")
    assert res.score_percentage == 100.0
    assert res.decision_correct
    assert res.constraints_respected
    assert res.action_appropriate
    assert res.validated_feedback

    node = erp_db.get_node("node_cdmx_roma")
    assert node.available_storage_m3 >= 0.0
    assert node.available_budget >= 0.0


@pytest.mark.asyncio
async def test_scenario_2_split_sourcing():
    """Supplier delivers 250/500 — agent must split-source the remaining 250."""
    res = await evaluate_scenario("scenario_2")
    assert res.score_percentage == 100.0
    assert res.decision_correct
    assert res.action_appropriate

    po = erp_db.purchase_orders["po_scenario_2"]
    assert po.confirmed_qty == 250
    assert po.status == "PARTIALLY_FULFILLED"


@pytest.mark.asyncio
async def test_scenario_3_surge_expansion():
    """Demand surge (+80%) should trigger an expanded order."""
    res = await evaluate_scenario("scenario_3")
    assert res.score_percentage == 100.0
    assert res.decision_correct
    assert res.validated_feedback


@pytest.mark.asyncio
async def test_scenario_4_reject_and_escalate():
    """Node at capacity — agent must reject and escalate to human."""
    res = await evaluate_scenario("scenario_4")
    assert res.score_percentage == 100.0
    assert res.decision_correct
    assert res.constraints_respected

    sp_pos = erp_db.get_open_pos(node_id="node_sao_paulo_pinheiros")
    assert len(sp_pos) == 0, "No PO should be created when rejecting"


def test_constraint_validator_blocks_overflow():
    """Directly test that 800 units at CDMX Roma fails validation."""
    val = validate_purchase_order_constraints(
        product_id="prod_oat_milk_barista",
        node_id="node_cdmx_roma",
        supplier_id="supp_oat_master",
        quantity=800
    )
    assert val.is_valid is False
    assert val.storage_ok is False
    assert any("m3" in v for v in val.violations)
    assert val.remediation_suggestion is not None


@pytest.mark.asyncio
async def test_full_evaluation():
    result = await run_full_evaluation()
    assert result["overall_status"] == "PASSED"
    assert result["overall_evaluation_score"] == 100.0
    assert result["total_scenarios_evaluated"] == 4
