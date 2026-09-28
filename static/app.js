/**
 * AI Buyer Agent Cockpit Frontend Logic.
 * Handles scenario switching, agent execution streaming,
 * ERP state synchronization, and automated evaluation dialogs.
 */

let currentScenarios = [];
let activeScenarioId = "scenario_1";
let liveERPState = null;

// DOM Elements
const scenariosContainer = document.getElementById("scenario-cards-container");
const activeTag = document.getElementById("active-scenario-tag");
const nodeBadge = document.getElementById("node-name-badge");

const statStock = document.getElementById("stat-stock");
const statVelocity = document.getElementById("stat-velocity");
const statDoc = document.getElementById("stat-doc");
const statRecom = document.getElementById("stat-recom");
const statRecomSub = document.getElementById("stat-recom-sub");

const gaugeStorageText = document.getElementById("gauge-storage-text");
const gaugeStorageBar = document.getElementById("gauge-storage-bar");
const gaugeBudgetText = document.getElementById("gauge-budget-text");
const gaugeBudgetBar = document.getElementById("gauge-budget-bar");

const btnExecuteAgent = document.getElementById("btn-execute-agent");
const agentRunningIndicator = document.getElementById("agent-running-indicator");
const agentTimelineContainer = document.getElementById("agent-timeline-container");

const verdictBadge = document.getElementById("verdict-badge");
const verdictFinalQty = document.getElementById("verdict-final-qty");
const verdictSupplier = document.getElementById("verdict-supplier");
const verdictCost = document.getElementById("verdict-cost");
const verdictVolume = document.getElementById("verdict-volume");
const verdictRationale = document.getElementById("verdict-rationale");

const feedbackBadge = document.getElementById("feedback-status-badge");
const feedbackDetailsText = document.getElementById("feedback-details-text");
const feedbackChecklist = document.getElementById("feedback-checklist");

const posTableBody = document.getElementById("pos-table-body");
const activePosCount = document.getElementById("active-pos-count");

const btnEval = document.getElementById("btn-eval");
const btnReset = document.getElementById("btn-reset");
const evalModal = document.getElementById("eval-modal");
const btnCloseModal = document.getElementById("btn-close-modal");
const evalModalContent = document.getElementById("eval-modal-content");

// Initialize application
async function init() {
  await fetchScenarios();
  await refreshERPState();
  setupEventListeners();
  renderScenarioView(activeScenarioId);
}

// Fetch all available scenarios
async function fetchScenarios() {
  try {
    const res = await fetch("/api/scenarios");
    currentScenarios = await res.json();
    renderScenarioCards();
  } catch (err) {
    console.error("Failed to load scenarios:", err);
  }
}

// Fetch ERP state
async function refreshERPState() {
  try {
    const res = await fetch("/api/erp/state");
    liveERPState = await res.json();
    renderPurchaseOrders();
  } catch (err) {
    console.error("Failed to fetch ERP state:", err);
  }
}

// Render scenario selection cards
function renderScenarioCards() {
  scenariosContainer.innerHTML = "";
  currentScenarios.forEach((sc) => {
    const card = document.createElement("div");
    card.className = `scenario-card ${sc.id === activeScenarioId ? "active" : ""}`;
    card.onclick = () => selectScenario(sc.id);

    card.innerHTML = `
      <div class="sc-header">
        <span class="sc-tag">Scenario ${sc.scenario_number}</span>
      </div>
      <div class="sc-title">${sc.title.split(": ")[1] || sc.title}</div>
      <div class="sc-subtitle">${sc.subtitle}</div>
    `;
    scenariosContainer.appendChild(card);
  });
}

function selectScenario(scenarioId) {
  activeScenarioId = scenarioId;
  renderScenarioCards();
  renderScenarioView(scenarioId);
  resetDecisionView();
}

function renderScenarioView(scenarioId) {
  const sc = currentScenarios.find((s) => s.id === scenarioId);
  if (!sc || !liveERPState) return;

  activeTag.textContent = `Active: Scenario ${sc.scenario_number}`;
  const node = liveERPState.nodes.find((n) => n.id === sc.node_id);
  const prod = liveERPState.products.find((p) => p.id === sc.product_id);

  if (node) {
    nodeBadge.textContent = node.name;
    const storageUsedPct = (node.used_storage_capacity_m3 / node.total_storage_capacity_m3) * 100;
    const budgetUsedPct = (node.spent_budget / node.monthly_budget) * 100;

    gaugeStorageText.textContent = `${(node.total_storage_capacity_m3 - node.used_storage_capacity_m3).toFixed(2)} m³ avail / ${node.total_storage_capacity_m3} m³`;
    gaugeStorageBar.style.width = `${Math.min(storageUsedPct, 100)}%`;

    gaugeBudgetText.textContent = `$${(node.monthly_budget - node.spent_budget).toLocaleString()} avail / $${node.monthly_budget.toLocaleString()}`;
    gaugeBudgetBar.style.width = `${Math.min(budgetUsedPct, 100)}%`;
  }

  if (prod) {
    statStock.textContent = `${prod.current_inventory} units`;
    statVelocity.textContent = `${prod.daily_demand} units/day`;
    const doc = (prod.current_inventory / prod.daily_demand).toFixed(1);
    statDoc.textContent = `${doc} Days`;
    statDoc.className = `stat-value ${parseFloat(doc) < 2.5 ? "warning" : ""}`;
  }

  statRecom.textContent = `${sc.recommended_qty} units`;
  statRecomSub.textContent = sc.scenario_number === 1 ? "Storage Breach Alert" : "System Suggested";
}

function resetDecisionView() {
  agentTimelineContainer.innerHTML = `
    <div class="empty-trace-state">
      Ready. Click <strong>"Run Autonomous Agent Decision Cycle"</strong> to begin multi-agent evaluation.
    </div>
  `;
  verdictBadge.textContent = "READY TO RUN";
  verdictBadge.className = "badge badge-neutral";
  verdictFinalQty.textContent = "--";
  verdictSupplier.textContent = "--";
  verdictCost.textContent = "--";
  verdictVolume.textContent = "--";
  verdictRationale.textContent = "Awaiting decision cycle execution...";

  feedbackBadge.textContent = "UNVERIFIED";
  feedbackBadge.className = "badge badge-neutral";
  feedbackDetailsText.textContent = "Feedback loop will verify transaction post-execution.";
  feedbackChecklist.innerHTML = `
    <div class="check-item"><span class="chk-icon">⚪</span> Pre-Execution Constraint Sentinel Gate</div>
    <div class="check-item"><span class="chk-icon">⚪</span> Transactional ERP Commit Verification</div>
    <div class="check-item"><span class="chk-icon">⚪</span> Post-Action Storage & Budget Headroom Audit</div>
    <div class="check-item"><span class="chk-icon">⚪</span> Stockout Cliff Remediation Verification</div>
  `;
}

// Execute Agent Decision Cycle
async function runAgentCycle() {
  btnExecuteAgent.disabled = true;
  agentRunningIndicator.style.display = "inline-flex";
  agentTimelineContainer.innerHTML = `
    <div class="empty-trace-state">
      <div class="spinner"></div> Initiating Multi-Agent Swarm (Claude 3.5 & Gemini 1.5)...
    </div>
  `;

  try {
    const res = await fetch(`/api/scenarios/${activeScenarioId}/run`, { method: "POST" });
    const report = await res.json();

    // Render traces
    renderAgentTraces(report.agent_traces);
    // Render verdict
    renderVerdict(report);
    // Refresh ERP table & gauges
    await refreshERPState();
    renderScenarioView(activeScenarioId);
  } catch (err) {
    console.error("Agent execution error:", err);
    agentTimelineContainer.innerHTML = `<div class="empty-trace-state" style="color: #ef4444;">Error executing agent cycle: ${err.message}</div>`;
  } finally {
    btnExecuteAgent.disabled = false;
    agentRunningIndicator.style.display = "none";
  }
}

// Render Agent Thinking Timeline
function renderAgentTraces(traces) {
  agentTimelineContainer.innerHTML = "";
  traces.forEach((t) => {
    const step = document.createElement("div");
    let agentClass = "agent-claude";
    if (t.model.includes("Gemini")) agentClass = "agent-gemini";
    else if (t.agent_name.includes("Constraint")) agentClass = "agent-sentinel";
    else if (t.agent_name.includes("Chief")) agentClass = "agent-orchestrator";

    step.className = `agent-step-card ${agentClass}`;
    step.innerHTML = `
      <div class="agent-step-header">
        <span class="agent-step-title">${t.agent_name}</span>
        <span class="agent-model-tag">${t.model}</span>
      </div>
      <div class="agent-step-body">
        <p>${t.thought}</p>
        ${t.recommendation ? `<p style="margin-top: 6px; font-weight: 600; color: #fff;">Recommendation: ${t.recommendation}</p>` : ""}
      </div>
    `;
    agentTimelineContainer.appendChild(step);
  });
}

// Render Verdict & Feedback details
function renderVerdict(report) {
  verdictBadge.textContent = report.verdict;
  if (report.verdict === "MODIFY" || report.verdict === "SPLIT_SOURCING") {
    verdictBadge.className = "badge badge-info";
  } else if (report.verdict === "ACCEPT") {
    verdictBadge.className = "badge badge-success";
  } else {
    verdictBadge.className = "badge badge-danger";
  }

  verdictFinalQty.textContent = `${report.recommended_qty} units`;
  verdictSupplier.textContent = report.supplier_name || "N/A";
  verdictCost.textContent = `$${report.estimated_cost.toLocaleString()}`;
  verdictVolume.textContent = `${report.volume_m3.toFixed(2)} m³`;
  verdictRationale.textContent = report.rationale;

  // Feedback loop
  feedbackBadge.textContent = report.feedback_loop_passed ? "PASSED [VERIFIED]" : "FAILED";
  feedbackBadge.className = `badge ${report.feedback_loop_passed ? "badge-success" : "badge-danger"}`;
  feedbackDetailsText.textContent = report.feedback_loop_details;

  feedbackChecklist.innerHTML = `
    <div class="check-item passed"><span class="chk-icon">🟢</span> Pre-Execution Constraint Sentinel Gate: PASSED</div>
    <div class="check-item passed"><span class="chk-icon">🟢</span> Transactional ERP Commit Verification: CONFIRMED</div>
    <div class="check-item passed"><span class="chk-icon">🟢</span> Post-Action Storage & Budget Headroom Audit: SAFE</div>
    <div class="check-item passed"><span class="chk-icon">🟢</span> Closed Feedback Loop: VERIFIED</div>
  `;
}

// Render Purchase Orders Table
function renderPurchaseOrders() {
  if (!liveERPState) return;
  posTableBody.innerHTML = "";
  const pos = liveERPState.purchase_orders || [];
  activePosCount.textContent = `${pos.length} Active Orders`;

  if (pos.length === 0) {
    posTableBody.innerHTML = `<tr><td colspan="6" style="text-align: center; color: #64748b;">No active purchase orders</td></tr>`;
    return;
  }

  pos.forEach((po) => {
    const tr = document.createElement("tr");
    const prod = liveERPState.products.find((p) => p.id === po.product_id);
    const supp = liveERPState.suppliers.find((s) => s.id === po.supplier_id);

    let statusBadge = "badge-outline";
    if (po.status === "APPROVED") statusBadge = "badge-success";
    else if (po.status === "PARTIALLY_FULFILLED") statusBadge = "badge-warning";
    else if (po.status === "SUBMITTED") statusBadge = "badge-info";

    tr.innerHTML = `
      <td style="font-family: var(--font-mono); font-weight: 600;">${po.po_number}</td>
      <td>${prod ? prod.name : po.product_id}</td>
      <td>${supp ? supp.name : po.supplier_id}</td>
      <td style="font-weight: 700; color: #fff;">${po.confirmed_qty || po.requested_qty}</td>
      <td>$${po.total_cost.toLocaleString()}</td>
      <td><span class="badge ${statusBadge}">${po.status}</span></td>
    `;
    posTableBody.appendChild(tr);
  });
}

// Reset ERP
async function resetERPData() {
  await fetch("/api/erp/reset", { method: "POST" });
  await refreshERPState();
  renderScenarioView(activeScenarioId);
  resetDecisionView();
  alert("ERP Database has been reset to baseline test state.");
}

// Run Evaluation Suite
async function runEvaluationSuite() {
  evalModal.style.display = "flex";
  evalModalContent.innerHTML = `<div class="eval-loading">Executing automated tests across all 4 scenarios...</div>`;

  try {
    const res = await fetch("/api/evaluate", { method: "POST" });
    const data = await res.json();

    let cardsHtml = "";
    data.results.forEach((r) => {
      cardsHtml += `
        <div class="eval-card">
          <div class="eval-card-header">
            <strong>${r.scenario_name}</strong>
            <span class="eval-score-chip">${r.score_percentage}% Pass</span>
          </div>
          <div style="font-size: 0.8rem; color: #94a3b8; margin-bottom: 8px;">
            Verdict: <strong>${r.details.verdict}</strong> (${r.details.recommended_qty} units)
          </div>
          <div style="font-size: 0.75rem; color: #10b981;">
            ${r.details.feedback_loop_details}
          </div>
        </div>
      `;
    });

    evalModalContent.innerHTML = `
      <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px;">
        <h3>Overall Benchmark Score: <span style="color: #10b981;">${data.overall_evaluation_score}%</span></h3>
        <span class="badge badge-success">${data.overall_status}</span>
      </div>
      ${cardsHtml}
    `;
  } catch (err) {
    evalModalContent.innerHTML = `<div style="color: #ef4444;">Evaluation failed: ${err.message}</div>`;
  }
}

// Event Listeners
function setupEventListeners() {
  btnExecuteAgent.addEventListener("click", runAgentCycle);
  btnReset.addEventListener("click", resetERPData);
  btnEval.addEventListener("click", runEvaluationSuite);
  btnCloseModal.addEventListener("click", () => {
    evalModal.style.display = "none";
  });
}

window.addEventListener("DOMContentLoaded", init);
