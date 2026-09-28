"""
Agent 3 — Constraint validation (deterministic, no LLM).

Checks whether a proposed order quantity fits within the node's physical
storage capacity, remaining budget, supplier MOQ, and shelf-life limits.
Returns a structured pass/fail result with violation details.
"""
from src.erp_tools import get_node_constraints, validate_purchase_order_constraints
from src.models import AgentTraceStep, ValidationResult


class ConstraintValidatorAgent:
    def __init__(self):
        self.name = "Constraint Validator"
        self.role = "Storage, budget, and MOQ checks"
        self.model = "Deterministic (rule-based)"

    def validate(
        self,
        product_id: str,
        node_id: str,
        supplier_id: str,
        target_quantity: int
    ) -> AgentTraceStep:
        node_status = get_node_constraints(node_id)
        result: ValidationResult = validate_purchase_order_constraints(
            product_id=product_id,
            node_id=node_id,
            supplier_id=supplier_id,
            quantity=target_quantity
        )

        status_label = "PASS" if result.is_valid else "FAIL"
        thought = (
            f"Validated {target_quantity} units against {node_status.get('node_name')}: "
            f"storage {node_status.get('available_storage_m3')} m3, "
            f"budget ${node_status.get('available_budget'):,.0f}. "
            f"Result: {status_label}."
        )

        return AgentTraceStep(
            agent_name=self.name,
            role=self.role,
            model=self.model,
            thought=thought,
            findings={
                "node_status": node_status,
                "is_valid": result.is_valid,
                "budget_ok": result.budget_ok,
                "storage_ok": result.storage_ok,
                "moq_ok": result.moq_ok,
                "shelf_life_ok": result.shelf_life_ok,
                "violations": result.violations,
                "remediation_suggestion": result.remediation_suggestion
            },
            recommendation=(
                result.remediation_suggestion
                or "All constraints satisfied."
            )
        )
