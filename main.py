"""
FastAPI Server & REST API for AI Buyer Agent.
Provides endpoints for executing agent cycles, inspecting ERP telemetry,
triggering automated evaluation benchmarks, and serving the interactive Cockpit UI.
"""
import os
import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from src.config import settings
from src.erp_database import erp_db
from src.agents.buyer_orchestrator import buyer_orchestrator
from src.evaluation import evaluate_scenario, run_full_evaluation
from src.models import Scenario

app = FastAPI(
    title="AI Buyer Agent - Autonomous Purchasing System",
    description="Full-stack AI Purchasing Agent for Retail and Quick-Commerce Fulfillment Networks.",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Serve static dashboard assets
static_dir = os.path.join(os.path.dirname(__file__), "static")
if os.path.exists(static_dir):
    app.mount("/static", StaticFiles(directory=static_dir), name="static")


@app.get("/")
async def get_index():
    index_path = os.path.join(static_dir, "index.html")
    if os.path.exists(index_path):
        return FileResponse(index_path)
    return {"message": "AI Buyer Agent API is running. Access /docs for Swagger specifications."}


@app.get("/api/scenarios")
async def list_scenarios():
    """List all available purchasing scenarios."""
    return list(erp_db.scenarios.values())


@app.get("/api/scenarios/{scenario_id}")
async def get_scenario(scenario_id: str):
    """Retrieve details for a specific scenario."""
    sc = erp_db.scenarios.get(scenario_id)
    if not sc:
        raise HTTPException(status_code=404, detail="Scenario not found")
    return sc


@app.post("/api/scenarios/{scenario_id}/run")
async def run_scenario(scenario_id: str):
    """Trigger the multi-agent decision cycle for a scenario."""
    sc = erp_db.scenarios.get(scenario_id)
    if not sc:
        raise HTTPException(status_code=404, detail="Scenario not found")

    report = await buyer_orchestrator.run_purchasing_cycle(sc)
    return report.model_dump()


@app.get("/api/erp/state")
async def get_erp_state():
    """Inspect live ERP database state: nodes, inventory, and open purchase orders."""
    return {
        "nodes": list(erp_db.nodes.values()),
        "products": list(erp_db.products.values()),
        "suppliers": list(erp_db.suppliers.values()),
        "purchase_orders": list(erp_db.purchase_orders.values())
    }


@app.post("/api/erp/reset")
async def reset_erp():
    """Reset ERP state to pristine benchmark baseline."""
    erp_db.reset()
    return {"status": "success", "message": "ERP database reset to initial baseline."}


@app.post("/api/evaluate")
async def evaluate_all():
    """Execute full evaluation benchmark across all test scenarios."""
    results = await run_full_evaluation()
    return results


class ApprovalRequest(BaseModel):
    scenario_id: str
    action: str  # APPROVE or OVERRIDE
    notes: str = ""


@app.post("/api/approve")
async def approve_action(req: ApprovalRequest):
    """Human-in-the-loop sign-off or policy override."""
    return {
        "status": "RECORDED",
        "action": req.action,
        "notes": req.notes,
        "operator": "Human Category Lead (Authorized)"
    }


if __name__ == "__main__":
    uvicorn.run("main:app", host=settings.HOST, port=settings.PORT, reload=settings.DEBUG)
