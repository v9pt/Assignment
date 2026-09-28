"""
Agent 1: Inventory & Demand Intelligence Specialist (Powered by Gemini)
Role: Deep telemetry research, sales velocity analysis, burn-rate calculation,
forecast anomaly detection, and days-of-coverage (DOC) modeling.
"""
import json
from typing import Dict, Any
from src.llm_client import llm_client
from src.erp_tools import get_inventory_and_forecast
from src.models import AgentTraceStep


class InventoryAnalystAgent:
    def __init__(self):
        self.name = "Inventory & Demand Specialist"
        self.role = "Demand Forecasting & Burn Rate Telemetry"
        self.model = "Google Gemini 1.5 Pro"

    async def analyze(
        self,
        product_id: str,
        node_id: str,
        recommended_qty: int,
        context_notes: str = ""
    ) -> AgentTraceStep:
        # 1. Fetch live telemetry from ERP
        telemetry = get_inventory_and_forecast(product_id, node_id)

        # 2. Build Prompt for Gemini
        system_prompt = (
            "You are an expert Inventory & Demand Intelligence AI for a quick-commerce network. "
            "Your objective is to critically audit incoming replenishment recommendations. "
            "Never assume recommendations are correct. Calculate burn rates, days of coverage (DOC), "
            "spoilage risks, and determine the exact mathematically justified replenishment need."
        )

        user_prompt = f"""
Current Inventory Telemetry:
{json.dumps(telemetry, indent=2)}

Initial Purchasing System Recommendation: {recommended_qty} units
Context Notes: {context_notes}

Analyze this situation:
1. Is the recommended quantity ({recommended_qty} units) mathematically sound, an over-order, or an under-order?
2. What are the Current Days of Coverage (DOC) vs Target DOC?
3. What is the stockout risk or spoilage risk?
4. What is your calibrated demand recommendation?

Respond in structured JSON format with keys:
- analysis (str)
- healthy_coverage_target_days (float)
- adjusted_demand_need (int)
- stockout_risk_score (float 0.0-1.0)
- justification (str)
"""
        response_text = await llm_client.call_gemini(system_prompt, user_prompt)

        try:
            findings = json.loads(response_text)
        except Exception:
            findings = {
                "raw_response": response_text,
                "adjusted_demand_need": recommended_qty,
                "stockout_risk_score": 0.5
            }

        thought_summary = (
            f"Audited recommendation of {recommended_qty} units against current inventory ({telemetry.get('current_inventory')} units) "
            f"and daily sales velocity ({telemetry.get('daily_demand_units')} units/day). "
            f"Calibrated replenishment target: {findings.get('adjusted_demand_need', recommended_qty)} units."
        )

        return AgentTraceStep(
            agent_name=self.name,
            role=self.role,
            model=self.model,
            thought=thought_summary,
            findings={
                "erp_telemetry": telemetry,
                "gemini_intelligence": findings
            },
            recommendation=str(findings.get("justification", findings.get("analysis", "")))
        )
