"""
FastAPI application — serves the REST API and the dashboard UI.
"""
import os
import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from src.config import settings
from src.erp_database import erp_db
from src.agents.buyer_orchestrator import buyer_orchestrator
from src.evaluation import evaluate_scenario, run_full_evaluation

app = FastAPI(title="AI Buyer Agent", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

static_dir = os.path.join(os.path.dirname(__file__), "static")
if os.path.exists(static_dir):
    app.mount("/static", StaticFiles(directory=static_dir), name="static")


@app.get("/")
async def index():
    path = os.path.join(static_dir, "index.html")
    if os.path.exists(path):
        return FileResponse(path)
    return {"status": "running"}


@app.get("/api/scenarios")
async def list_scenarios():
    return list(erp_db.scenarios.values())


@app.get("/api/scenarios/{scenario_id}")
async def get_scenario(scenario_id: str):
    sc = erp_db.scenarios.get(scenario_id)
    if not sc:
        raise HTTPException(404, "Scenario not found")
    return sc


@app.post("/api/scenarios/{scenario_id}/run")
async def run_scenario(scenario_id: str):
    """Execute the multi-agent purchasing cycle for a scenario."""
    sc = erp_db.scenarios.get(scenario_id)
    if not sc:
        raise HTTPException(404, "Scenario not found")
    report = await buyer_orchestrator.run_purchasing_cycle(sc)
    return report.model_dump()


@app.get("/api/erp/state")
async def get_erp_state():
    """Dump the current ERP state (nodes, products, suppliers, POs)."""
    return {
        "nodes": list(erp_db.nodes.values()),
        "products": list(erp_db.products.values()),
        "suppliers": list(erp_db.suppliers.values()),
        "purchase_orders": list(erp_db.purchase_orders.values())
    }


@app.post("/api/erp/reset")
async def reset_erp():
    erp_db.reset()
    return {"status": "ok"}


@app.post("/api/evaluate")
async def evaluate_all():
    """Run evaluation across all four scenarios."""
    return await run_full_evaluation()


class ApprovalRequest(BaseModel):
    scenario_id: str
    action: str
    notes: str = ""


@app.post("/api/approve")
async def approve_action(req: ApprovalRequest):
    """Record a human approval or override."""
    return {"status": "recorded", "action": req.action, "notes": req.notes}


if __name__ == "__main__":
    uvicorn.run("main:app", host=settings.HOST, port=settings.PORT, reload=settings.DEBUG)
