"""
Agent 2 — Supplier sourcing and allocation.

Given a target quantity and product, evaluates the available supplier pool
(prices, lead times, MOQs, reliability) and recommends an allocation strategy.
Uses Claude for the reasoning step.
"""
import json
from src.llm_client import llm_client
from src.erp_tools import get_available_suppliers
from src.models import AgentTraceStep


class SourcingSpecialistAgent:
    def __init__(self):
        self.name = "Sourcing Specialist"
        self.role = "Supplier evaluation & allocation"
        self.model = "Claude Sonnet 4"

    async def evaluate_sourcing(
        self,
        product_id: str,
        target_quantity: int,
        shortfall_deficit: int = 0,
        context_notes: str = ""
    ) -> AgentTraceStep:
        suppliers = get_available_suppliers(product_id)

        system_prompt = (
            "You are a procurement specialist. Evaluate available suppliers "
            "and recommend an allocation strategy considering MOQs, lead times, "
            "unit prices, and reliability scores. Return a JSON object."
        )

        user_prompt = f"""
Product: {product_id}
Quantity needed: {target_quantity} units
Shortfall from primary supplier: {shortfall_deficit} units
Context: {context_notes}

Suppliers:
{json.dumps(suppliers, indent=2)}

Questions:
1. Which supplier should fill this order?
2. Should we split across suppliers?
3. Does the quantity meet MOQ?
4. Optimal allocation?

Return JSON: recommended_supplier_id, supplier_name, allocation_strategy,
allocated_quantity, unit_price, lead_time_days, rationale.
"""
        raw = await llm_client.call_claude(system_prompt, user_prompt)

        try:
            findings = json.loads(raw)
        except Exception:
            primary = suppliers[0] if suppliers else {}
            findings = {
                "recommended_supplier_id": primary.get("supplier_id", ""),
                "supplier_name": primary.get("supplier_name", ""),
                "allocation_strategy": "PRIMARY",
                "allocated_quantity": target_quantity,
                "unit_price": primary.get("unit_price", 0.0),
                "lead_time_days": primary.get("lead_time_days", 2),
                "rationale": "Defaulted to top-ranked supplier."
            }

        thought = (
            f"Evaluated {len(suppliers)} suppliers for {product_id}. "
            f"Selected {findings.get('supplier_name')} for {findings.get('allocated_quantity')} units "
            f"@ ${findings.get('unit_price')}/unit, {findings.get('lead_time_days')}d lead time."
        )

        return AgentTraceStep(
            agent_name=self.name,
            role=self.role,
            model=self.model,
            thought=thought,
            findings={"available_suppliers": suppliers, "sourcing_strategy": findings},
            recommendation=findings.get("rationale")
        )
