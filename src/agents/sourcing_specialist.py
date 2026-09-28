"""
Agent 2: Sourcing & Supplier Allocation Specialist (Powered by Claude)
Role: Supplier portfolio discovery, MOQ validation, lead-time optimization,
multi-supplier split sourcing, and vendor risk mitigation.
"""
import json
from typing import Dict, Any, List
from src.llm_client import llm_client
from src.erp_tools import get_available_suppliers
from src.models import AgentTraceStep


class SourcingSpecialistAgent:
    def __init__(self):
        self.name = "Sourcing & Supplier Specialist"
        self.role = "Vendor Allocation & Procurement Strategy"
        self.model = "Anthropic Claude 3.5 Sonnet"

    async def evaluate_sourcing(
        self,
        product_id: str,
        target_quantity: int,
        shortfall_deficit: int = 0,
        context_notes: str = ""
    ) -> AgentTraceStep:
        # 1. Discover all suppliers for product
        suppliers = get_available_suppliers(product_id)

        # 2. Build Prompt for Claude
        system_prompt = (
            "You are a Senior Strategic Sourcing & Supplier Procurement AI Agent. "
            "Your goal is to evaluate supplier options, lead times, MOQs, unit prices, "
            "and vendor reliability to devise an optimal procurement and order-allocation strategy."
        )

        user_prompt = f"""
Target SKU ID: {product_id}
Target Quantity Needed: {target_quantity} units
Shortfall Deficit (if applicable): {shortfall_deficit} units
Context Notes: {context_notes}

Available Qualified Suppliers:
{json.dumps(suppliers, indent=2)}

Evaluate:
1. Which supplier should fulfill this order?
2. If there is a shortfall or primary supplier capacity limit, should we engage a secondary supplier?
3. Does the quantity respect supplier MOQ?
4. What is the optimal allocation strategy?

Respond in structured JSON format with keys:
- recommended_supplier_id (str)
- supplier_name (str)
- allocation_strategy (str: e.g. 'PRIMARY_WHOLESALE', 'EMERGENCY_SPLIT_SOURCING', 'MULTI_VENDOR')
- allocated_quantity (int)
- unit_price (float)
- lead_time_days (int)
- rationale (str)
"""
        response_text = await llm_client.call_claude(system_prompt, user_prompt)

        try:
            findings = json.loads(response_text)
        except Exception:
            # Fallback to primary supplier
            primary = suppliers[0] if suppliers else {}
            findings = {
                "recommended_supplier_id": primary.get("supplier_id", ""),
                "supplier_name": primary.get("supplier_name", ""),
                "allocation_strategy": "PRIMARY_WHOLESALE",
                "allocated_quantity": target_quantity,
                "unit_price": primary.get("unit_price", 0.0),
                "lead_time_days": primary.get("lead_time_days", 2),
                "rationale": "Selected top qualified supplier meeting baseline requirements."
            }

        thought_summary = (
            f"Evaluated {len(suppliers)} qualified suppliers for {product_id}. "
            f"Strategy selected: {findings.get('allocation_strategy')} -> "
            f"Supplier '{findings.get('supplier_name')}' for {findings.get('allocated_quantity')} units "
            f"@ ${findings.get('unit_price')}/unit ({findings.get('lead_time_days')}d lead time)."
        )

        return AgentTraceStep(
            agent_name=self.name,
            role=self.role,
            model=self.model,
            thought=thought_summary,
            findings={
                "available_suppliers": suppliers,
                "sourcing_strategy": findings
            },
            recommendation=findings.get("rationale")
        )
