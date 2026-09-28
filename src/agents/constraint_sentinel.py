"""
Agent 3: Constraint & Financial Risk Sentinel (Deterministic Mathematical Core)
Role: Enforces strict physical warehouse space (m3), monthly purchasing budget limits,
supplier MOQ thresholds, and perishable shelf-life boundaries.
"""
from typing import Dict, Any, Optional
from src.erp_tools import get_node_constraints, validate_purchase_order_constraints
from src.models import AgentTraceStep, ValidationResult


class ConstraintSentinelAgent:
    def __init__(self):
        self.name = "Constraint & Financial Sentinel"
        self.role = "Deterministic Capacity & Budget Guardrail"
        self.model = "Mathematical Constraint Solver & Safety Guard"

    def audit_constraints(
        self,
        product_id: str,
        node_id: str,
        supplier_id: str,
        target_quantity: int
    ) -> AgentTraceStep:
        node_status = get_node_constraints(node_id)
        validation: ValidationResult = validate_purchase_order_constraints(
            product_id=product_id,
            node_id=node_id,
            supplier_id=supplier_id,
            quantity=target_quantity
        )

        thought_summary = (
            f"Audited {target_quantity} units against Node '{node_status.get('node_name')}'. "
            f"Available Storage: {node_status.get('available_storage_m3')} m3 | "
            f"Available Budget: ${node_status.get('available_budget'):,}. "
            f"Constraint Status: {'PASSED [OK]' if validation.is_valid else 'VIOLATION DETECTED [REJECT/REMEDIATE]'}."
        )

        return AgentTraceStep(
            agent_name=self.name,
            role=self.role,
            model=self.model,
            thought=thought_summary,
            findings={
                "node_status": node_status,
                "is_valid": validation.is_valid,
                "budget_ok": validation.budget_ok,
                "storage_ok": validation.storage_ok,
                "moq_ok": validation.moq_ok,
                "shelf_life_ok": validation.shelf_life_ok,
                "violations": validation.violations,
                "remediation_suggestion": validation.remediation_suggestion
            },
            recommendation=validation.remediation_suggestion or "All physical and fiscal constraints satisfied."
        )
