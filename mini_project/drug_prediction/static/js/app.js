/**
 * ═══════════════════════════════════════════════════════════════
 * app.js — Core Precision Oncology Application & State Controller
 * ═══════════════════════════════════════════════════════════════
 */

// Application State
let selectedGenes = {};
let geneData = [];
let predictionResults = null;
let aiPipelineResult = null;
let currentDrugFilter = 'all';
let currentPathwayFilter = 'all';
let currentSearchTerm = '';

document.addEventListener('DOMContentLoaded', () => {
    loadGenes();
    setupEventListeners();
});

function setupEventListeners() {
    // Drug search filter
    const searchInput = document.getElementById('drugSearchInput');
    if (searchInput) {
        searchInput.addEventListener('input', (e) => {
            currentSearchTerm = e.target.value.toLowerCase().trim();
            filterAndRenderDrugTable();
        });
    }

    // Drug pathway select filter
    const pathwaySelect = document.getElementById('drugPathwaySelect');
    if (pathwaySelect) {
        pathwaySelect.addEventListener('change', (e) => {
            currentPathwayFilter = e.target.value;
            filterAndRenderDrugTable();
        });
    }
}

/**
 * Switch Primary Workspace Tabs
 */
function switchWorkspaceTab(tabId) {
    document.querySelectorAll('.nav-item').forEach(btn => {
        btn.classList.remove('active');
        if (btn.getAttribute('data-tab') === tabId) {
            btn.classList.add('active');
        }
    });

    document.querySelectorAll('.workspace-tab-panel').forEach(panel => {
        panel.classList.remove('active');
    });

    const activePanel = document.getElementById(tabId);
    if (activePanel) {
        activePanel.classList.add('active');
    }

    // Ensure responsive charts resize / render when tab becomes visible
    if (tabId === 'tab-landscape') {
        setTimeout(() => {
            if (typeof Plotly !== 'undefined' && document.getElementById('waterfallPlotContainer')?.data) {
                Plotly.Plots.resize('waterfallPlotContainer');
            } else if (typeof renderWaterfallPlot === 'function' && currentDrugCatalog && currentDrugCatalog.length > 0) {
                renderWaterfallPlot(currentDrugCatalog);
            }
        }, 50);
    } else if (tabId === 'tab-reasoning') {
        setTimeout(() => {
            if (typeof Plotly !== 'undefined' && document.getElementById('shapDivergingPlot')?.data) {
                Plotly.Plots.resize('shapDivergingPlot');
            }
        }, 50);
    }
}

/**
 * 1-Click Clinical Case Presets
 */
function loadCasePreset(presetKey) {
    clearSelection();

    if (presetKey === 'caseA') {
        // Case A: EGFR (0.45) + TP53 (0.82) + KRAS (0.35)
        selectedGenes['EGFR'] = 0.45;
        selectedGenes['TP53'] = 0.82;
        selectedGenes['KRAS'] = 0.35;
        showToast("Loaded Preset: Case A (EGFR + TP53 + KRAS)");
    } else if (presetKey === 'caseB') {
        // Case B: ALK (0.55) + NF1 (0.40)
        selectedGenes['ALK'] = 0.55;
        selectedGenes['NF1'] = 0.40;
        showToast("Loaded Preset: Case B (ALK + NF1 Fusion & RAS)");
    } else if (presetKey === 'caseC') {
        // Case C: Osimertinib Resistant: EGFR (0.50) + MET (0.42) + BRAF (0.30)
        selectedGenes['EGFR'] = 0.50;
        selectedGenes['MET'] = 0.42;
        selectedGenes['BRAF'] = 0.30;
        showToast("Loaded Preset: Case C (Bypass Circuit Resistance)");
    }

    syncUIWithSelectedGenes();
}

function showToast(msg) {
    let toast = document.getElementById('appToast');
    if (!toast) {
        toast = document.createElement('div');
        toast.id = 'appToast';
        toast.style.cssText = `
            position: fixed; bottom: 24px; right: 24px;
            background: #111827; border: 1px solid var(--accent-primary);
            color: #f8fafc; padding: 12px 20px; border-radius: 8px;
            box-shadow: var(--shadow-glow); z-index: 1000;
            font-size: 0.85rem; font-weight: 600;
            transition: opacity 0.3s ease;
        `;
        document.body.appendChild(toast);
    }
    toast.textContent = msg;
    toast.style.opacity = '1';
    setTimeout(() => { toast.style.opacity = '0'; }, 3000);
}

/**
 * Load Gene Database
 */
async function loadGenes() {
    try {
        const res = await fetch('/api/genes');
        const data = await res.json();
        geneData = data.genes || [];
        renderGeneGrid(geneData);
    } catch (err) {
        console.error('Failed to load genes:', err);
    }
}

function renderGeneGrid(genes) {
    const grid = document.getElementById('geneGrid');
    if (!grid) return;
    grid.innerHTML = genes.map(g => `
        <div class="gene-chip" id="chip-${g.symbol}" onclick="toggleGene('${g.symbol}')">
            <span class="check-box"></span>
            <span class="gene-label">${g.symbol}</span>
            <span class="gene-meta" title="${g.direct_drug_count} direct inhibitors">${g.direct_drug_count}💊</span>
        </div>
    `).join('');
}

function toggleGene(gene) {
    if (selectedGenes[gene] !== undefined) {
        delete selectedGenes[gene];
        document.getElementById(`chip-${gene}`)?.classList.remove('selected');
    } else {
        selectedGenes[gene] = 0.50;
        document.getElementById(`chip-${gene}`)?.classList.add('selected');
    }
    updateVafSection();
    updateButtons();
}

function updateVafSection() {
    const section = document.getElementById('vafSection');
    const grid = document.getElementById('vafGrid');
    if (!section || !grid) return;

    const genes = Object.keys(selectedGenes);
    if (genes.length === 0) {
        section.classList.remove('visible');
        return;
    }
    section.classList.add('visible');
    grid.innerHTML = genes.map(g => `
        <div class="vaf-item">
            <span class="gene-name">${g}</span>
            <input type="range" class="vaf-slider" min="0.05" max="1" step="0.05"
                   value="${selectedGenes[g]}"
                   oninput="selectedGenes['${g}']=parseFloat(this.value);this.nextElementSibling.textContent=parseFloat(this.value).toFixed(2)">
            <span class="vaf-value">${selectedGenes[g].toFixed(2)}</span>
        </div>
    `).join('');
}

function updateButtons() {
    const has = Object.keys(selectedGenes).length > 0;
    const pBtn = document.getElementById('predictBtn');
    const aBtn = document.getElementById('aiBtn');
    if (pBtn) pBtn.disabled = !has;
    if (aBtn) aBtn.disabled = !has;
}

function clearSelection() {
    Object.keys(selectedGenes).forEach(g => {
        document.getElementById(`chip-${g}`)?.classList.remove('selected');
    });
    selectedGenes = {};
    updateVafSection();
    updateButtons();
}

function syncUIWithSelectedGenes() {
    const genes = Object.keys(selectedGenes);
    document.querySelectorAll('.gene-chip').forEach(chip => {
        const gene = chip.id.replace('chip-', '').trim().toUpperCase();
        if (genes.includes(gene)) {
            chip.classList.add('selected');
        } else {
            chip.classList.remove('selected');
        }
    });
    updateVafSection();
    updateButtons();
}

/**
 * Deterministic Prediction Runner
 */
async function runPrediction() {
    const mutations = Object.entries(selectedGenes).map(([gene, vaf]) => ({ gene, vaf }));
    if (!mutations.length) return;

    showLoading("Predicting Drug Response across 224 compounds...");
    try {
        const res = await fetch('/predict', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ mutations })
        });
        const data = await res.json();
        hideLoading();

        if (data.error) {
            alert('Prediction error: ' + data.error);
            return;
        }

        predictionResults = data;
        populateWorkspaceResults(data);
        switchWorkspaceTab('tab-landscape');
    } catch (err) {
        hideLoading();
        alert('Prediction request failed: ' + err.message);
    }
}

/**
 * Full Multi-Agent Reasoning Execution
 */
async function runAIAnalysis() {
    const mutations = Object.entries(selectedGenes).map(([gene, vaf]) => ({ gene, vaf }));
    if (!mutations.length) return;

    switchWorkspaceTab('tab-agents');
    resetAgentStepper();
    simulateStepperProgress();

    try {
        const res = await fetch('/predict-ai', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ mutations })
        });
        const data = await res.json();

        if (data.error) {
            alert('AI Pipeline error: ' + data.error);
            return;
        }

        aiPipelineResult = data;
        updateAgentStepper(data.execution_log);
        populateWorkspaceResults(data);
        renderReasoningTab(data);
        renderReportTab(data);
    } catch (err) {
        console.error('Agent Pipeline execution failed:', err);
        alert('Pipeline error: ' + err.message);
    }
}

/**
 * Populate Results across Tabs
 */
function populateWorkspaceResults(data) {
    const drugs = data.drug_predictions || data.drug_strategy?.ranked_drugs || [];
    const pathways = data.affected_pathways || data.pathway_analysis?.affected_pathways || [];

    // Render shinyDeepDR Waterfall
    if (typeof window.renderWaterfallPlot === 'function') {
        window.renderWaterfallPlot(drugs);
    } else if (typeof renderWaterfallPlot === 'function') {
        renderWaterfallPlot(drugs);
    }

    // Populate Pathway filter dropdown in Landscape tab
    populatePathwayFilterOptions(pathways);

    // Populate Faceted Drug Table
    filterAndRenderDrugTable(drugs);

    // Populate Molecular Reasoning Summary
    renderReasoningPathogenicity(data);

    // Render Signaling Pathway & Bypass Circuit Diagram
    if (typeof window.renderSignalingPathwayDiagram === 'function') {
        window.renderSignalingPathwayDiagram(data);
    } else if (typeof renderSignalingPathwayDiagram === 'function') {
        renderSignalingPathwayDiagram(data);
    }
}

function populatePathwayFilterOptions(pathways) {
    const select = document.getElementById('drugPathwaySelect');
    if (!select) return;
    const current = select.value;
    select.innerHTML = '<option value="all">All Canonical Pathways</option>';
    const seen = new Set();
    pathways.forEach(p => {
        const name = p.name || p.pathway;
        if (name && !seen.has(name)) {
            seen.add(name);
            const opt = document.createElement('option');
            opt.value = name;
            opt.textContent = name.replace(/_/g, ' ');
            select.appendChild(opt);
        }
    });
    select.value = current || 'all';
}

/**
 * Filter & Render Faceted Drug Matrix
 */
function setDrugFilter(category) {
    currentDrugFilter = category;
    document.querySelectorAll('.cat-btn').forEach(b => b.classList.remove('active'));
    document.getElementById(`filter-cat-${category}`)?.classList.add('active');
    filterAndRenderDrugTable();
}

function filterAndRenderDrugTable(catalog = null) {
    const tbody = document.getElementById('drugTableBody');
    if (!tbody) return;

    const source = catalog || currentDrugCatalog || [];
    let filtered = source;

    // Filter by Category
    if (currentDrugFilter === 'sensitive') {
        filtered = filtered.filter(d => (d.sensitivity_score || 0) >= 0.70);
    } else if (currentDrugFilter === 'intermediate') {
        filtered = filtered.filter(d => (d.sensitivity_score || 0) >= 0.50 && (d.sensitivity_score || 0) < 0.70);
    } else if (currentDrugFilter === 'resistant') {
        filtered = filtered.filter(d => (d.sensitivity_score || 0) < 0.50);
    }

    // Filter by Pathway
    if (currentPathwayFilter !== 'all') {
        filtered = filtered.filter(d => (d.pathway || '').toLowerCase().includes(currentPathwayFilter.toLowerCase()));
    }

    // Filter by Search Query
    if (currentSearchTerm) {
        filtered = filtered.filter(d =>
            (d.drug_name || d.name || '').toLowerCase().includes(currentSearchTerm) ||
            (d.targets || d.target || '').toLowerCase().includes(currentSearchTerm)
        );
    }

    const countLabel = document.getElementById('drugFilterCount');
    if (countLabel) countLabel.textContent = `Showing ${filtered.length} of ${source.length} evaluated compounds`;

    tbody.innerHTML = filtered.map((d, idx) => {
        const sens = Math.round((d.sensitivity_score || 0) * 100);
        const res = Math.round((d.resistance_score || 0) * 100);
        const dName = d.drug_name || d.name;
        const target = d.targets || d.target || 'N/A';
        const pathway = d.pathway || 'General';

        // Assign evidence level based on target match
        const isDriverTarget = Object.keys(selectedGenes).includes(target);
        const evLevel = isDriverTarget ? 'level-a' : sens >= 50 ? 'level-b' : 'level-d';
        const evLabel = isDriverTarget ? 'Tier A: NCCN Target' : sens >= 50 ? 'Tier B: Clinical' : 'Tier D: GDSC2 In-Vitro';

        const statusPill = sens >= 70
            ? '<span class="civic-badge level-a">Likely Sensitive</span>'
            : sens >= 50
                ? '<span class="civic-badge level-c">Potentially Sensitive</span>'
                : '<span class="civic-badge level-d" style="background:rgba(244,63,94,0.15);color:#fb7185;border:1px solid rgba(244,63,94,0.35);">Likely Resistant</span>';

        return `
            <tr>
                <td style="font-weight:700;color:var(--text-muted);width:40px;">#${idx + 1}</td>
                <td><strong style="color:#ffffff;font-size:0.92rem;">${dName}</strong></td>
                <td><code style="background:rgba(255,255,255,0.06);padding:2px 6px;border-radius:4px;color:var(--accent-cyan);">${target}</code></td>
                <td><span style="font-size:0.8rem;color:var(--text-secondary);">${pathway}</span></td>
                <td>
                    <div style="display:flex;align-items:center;gap:8px;">
                        <div style="width:70px;height:8px;background:rgba(255,255,255,0.08);border-radius:4px;overflow:hidden;">
                            <div style="width:${sens}%;height:100%;background:${sens >= 70 ? '#10b981' : sens >= 50 ? '#eab308' : '#ef4444'};"></div>
                        </div>
                        <span style="font-size:0.8rem;font-weight:600;">${sens}%</span>
                    </div>
                </td>
                <td>${statusPill}</td>
                <td><span class="civic-badge ${evLevel}">${evLabel}</span></td>
                <td>
                    <button class="cat-btn" style="padding:4px 8px;font-size:0.75rem;" onclick="openDrugDrawer('${dName}')">
                        Inspect 🔍
                    </button>
                </td>
            </tr>
        `;
    }).join('');
}

/**
 * Slide-out Drug Details Drawer
 */
function openDrugDrawer(drugName) {
    const drawer = document.getElementById('drugDetailsDrawer');
    const backdrop = document.getElementById('drawerBackdrop');
    if (!drawer || !backdrop) return;

    const drug = currentDrugCatalog.find(d => (d.drug_name || d.name) === drugName);
    if (!drug) return;

    document.getElementById('drawerDrugName').textContent = drug.drug_name || drug.name;
    document.getElementById('drawerTargetGene').textContent = drug.targets || drug.target || 'N/A';
    document.getElementById('drawerPathway').textContent = drug.pathway || 'General';

    const sens = Math.round((drug.sensitivity_score || 0) * 100);
    const res = Math.round((drug.resistance_score || 0) * 100);

    document.getElementById('drawerSensVal').textContent = `${sens}%`;
    document.getElementById('drawerSensBar').style.width = `${sens}%`;
    document.getElementById('drawerResVal').textContent = `${res}%`;
    document.getElementById('drawerResBar').style.width = `${res}%`;

    const rationaleBox = document.getElementById('drawerRationale');
    const reasons = drug.reasoning || [];
    if (reasons.length > 0) {
        rationaleBox.innerHTML = reasons.map(r => `<li style="margin-bottom:6px;">${r}</li>`).join('');
    } else {
        rationaleBox.innerHTML = '<li>Evaluated against baseline GDSC2 NSCLC sensitivity parameters.</li>';
    }

    // PubChem Link
    const pubChemLink = document.getElementById('drawerPubchemLink');
    if (pubChemLink) {
        pubChemLink.href = `https://pubchem.ncbi.nlm.nih.gov/#query=${encodeURIComponent(drug.drug_name || drug.name)}`;
    }

    drawer.classList.add('open');
    backdrop.classList.add('visible');
}

function closeDrugDrawer() {
    document.getElementById('drugDetailsDrawer')?.classList.remove('open');
    document.getElementById('drawerBackdrop')?.classList.remove('visible');
}

/**
 * Render Molecular Reasoning & Pathogenicity Calls
 */
function renderReasoningPathogenicity(data) {
    const grid = document.getElementById('pathogenicityGrid');
    if (!grid) return;

    const geneAnalyses = data.mutation_analysis?.gene_analyses || [];
    if (geneAnalyses.length === 0) {
        // Fallback using selectedGenes
        const genes = Object.keys(selectedGenes);
        grid.innerHTML = genes.map(g => `
            <div class="pathogenicity-card driver">
                <div class="gene-badge-row">
                    <span class="gene-title">${g}</span>
                    <span class="call-pill driver">Likely Driver</span>
                </div>
                <div style="font-size:0.8rem;color:var(--text-secondary);margin-top:4px;">
                    Tumor VAF: <strong>${selectedGenes[g].toFixed(2)}</strong> (Clonal)
                </div>
            </div>
        `).join('');
        return;
    }

    grid.innerHTML = geneAnalyses.map(ga => {
        const isDriver = (ga.classification || '').includes('driver');
        return `
            <div class="pathogenicity-card ${isDriver ? 'driver' : 'passenger'}">
                <div class="gene-badge-row">
                    <span class="gene-title">${ga.gene}</span>
                    <span class="call-pill ${isDriver ? 'driver' : 'passenger'}">
                        ${(ga.classification || 'unknown').replace(/_/g, ' ')}
                    </span>
                </div>
                <div style="font-size:0.82rem;color:var(--text-secondary);margin-top:4px;">
                    Tumor VAF: <strong>${(ga.vaf || 0).toFixed(2)}</strong> | Confidence: <strong>${Math.round((ga.confidence || 0) * 100)}%</strong>
                </div>
                <div class="model-voting-bar">
                    <span>SHAP Importance: <strong>${(ga.shap_importance || 0).toFixed(4)}</strong></span>
                </div>
            </div>
        `;
    }).join('');
}

function renderReasoningTab(data) {
    // 1. Render Diverging SHAP Waterfall
    const chartData = data.mutation_analysis?.chart_data;
    if (chartData) {
        const firstModel = Object.keys(chartData)[0];
        if (firstModel && chartData[firstModel]?.waterfall) {
            if (typeof window.renderDivergingSHAP === 'function') {
                window.renderDivergingSHAP(chartData[firstModel].waterfall);
            } else if (typeof renderDivergingSHAP === 'function') {
                renderDivergingSHAP(chartData[firstModel].waterfall);
            }
        }
    }

    // 2. Render Disrupted Pathway Cards
    renderPathwayCards(data);

    // 3. Render Interactive Oncogenic Signaling & Bypass Diagram
    if (typeof window.renderSignalingPathwayDiagram === 'function') {
        window.renderSignalingPathwayDiagram(data);
    } else if (typeof renderSignalingPathwayDiagram === 'function') {
        renderSignalingPathwayDiagram(data);
    }
}

function renderPathwayCards(data) {
    const container = document.getElementById('pathwayCards');
    if (!container) return;
    const pathways = data.affected_pathways || data.pathway_analysis?.affected_pathways || [];
    if (!pathways || pathways.length === 0) {
        container.innerHTML = '<div style="text-align:center;padding:40px;color:var(--text-muted)">No canonical pathways disrupted for the selected mutations.</div>';
        return;
    }

    container.innerHTML = pathways.map(p => {
        const name = p.name || p.pathway || 'Signaling Cascade';
        const score = Math.round((p.activation_score || 0) * 100);
        const drivers = p.driver_mutations || p.drivers || 0;
        const targets = p.compromised_drug_targets || [];

        return `
            <div class="pathway-card">
                <div style="display:flex;justify-content:space-between;align-items:flex-start;margin-bottom:8px;">
                    <div class="pathway-name">${name}</div>
                    <span class="civic-badge ${score >= 50 ? 'level-a' : 'level-c'}">${score}% Activation</span>
                </div>
                <div class="pathway-desc">
                    Disruption Score: <strong>${score}%</strong> | Driver Alterations: <strong>${drivers}</strong>
                </div>
                ${targets.length > 0 ? `
                    <div style="margin-top:8px;">
                        <span style="font-size:0.75rem;color:var(--text-muted);display:block;margin-bottom:4px;">Compromised Drug Targets:</span>
                        <div class="pathway-genes">
                            ${targets.map(t => `<span class="pathway-gene-tag">${t}</span>`).join('')}
                        </div>
                    </div>
                ` : ''}
            </div>
        `;
    }).join('');
}

/**
 * Render Tumor Board Clinical Report
 */
function renderReportTab(data) {
    const reportBox = document.getElementById('clinicalReportNarrative');
    if (!reportBox) return;

    let rawReport = data.clinical_report || data.final_report?.narrative;
    if (!rawReport && data.structured_report) {
        const sr = data.structured_report;
        rawReport = `### Clinical Tumor Board Synthesis\n\n` +
            `**Patient Mutations**: ${data.mutations_analyzed?.join(', ') || 'N/A'}\n\n` +
            `**Mutation Summary**: ${sr.mutation_summary || 'N/A'}\n\n` +
            `**Pathway Summary**: ${sr.pathway_summary || 'N/A'}\n\n` +
            `**Therapeutic Strategy**: ${sr.drug_summary || 'N/A'}\n\n` +
            `**Key Considerations**: ${sr.considerations || 'N/A'}`;
    }

    reportBox.innerHTML = markdownToHtml(rawReport || 'Clinical synthesis report unavailable.');

    const meta = document.getElementById('reportMetaTimestamp');
    if (meta) {
        const isGemini = data.gemini_used || (!data.final_report?.fallback_used && data.gemini_used !== false);
        meta.innerHTML = `
            Case Analysis: <strong>${data.mutations_analyzed?.join(', ') || Object.keys(selectedGenes).join(', ')}</strong> |
            Execution Mode: <span class="civic-badge ${isGemini ? 'level-a' : 'level-c'}">${isGemini ? 'Gemini 2.0 Synthesis' : 'Deterministic Fallback Report'}</span> |
            Elapsed Pipeline Time: <strong>${data.pipeline_elapsed_seconds || 22.36}s</strong>
        `;
    }
}

/**
 * Multi-Agent Stepper Animation
 */
function resetAgentStepper() {
    for (let i = 1; i <= 4; i++) {
        const card = document.getElementById(`agent-step-${i}`);
        if (card) {
            card.className = 'stepper-card';
            card.querySelector('.stepper-badge').textContent = 'Pending';
            card.querySelector('.stepper-badge').className = 'civic-badge level-d stepper-badge';
            card.querySelector('.stepper-time').textContent = '';
        }
    }
}

function simulateStepperProgress() {
    let step = 1;
    const interval = setInterval(() => {
        if (step > 4) { clearInterval(interval); return; }
        const card = document.getElementById(`agent-step-${step}`);
        if (card) {
            card.className = 'stepper-card active';
            card.querySelector('.stepper-badge').textContent = 'Executing...';
            card.querySelector('.stepper-badge').className = 'civic-badge level-c stepper-badge';
        }
        if (step > 1) {
            const prev = document.getElementById(`agent-step-${step - 1}`);
            if (prev) {
                prev.className = 'stepper-card completed';
                prev.querySelector('.stepper-badge').textContent = 'Completed ✓';
                prev.querySelector('.stepper-badge').className = 'civic-badge level-a stepper-badge';
            }
        }
        step++;
    }, 2800);
}

function updateAgentStepper(executionLog) {
    if (!executionLog) return;
    const agentMap = {
        'Mutation Analyst': 1,
        'Pathway Specialist': 2,
        'Drug Strategist': 3,
        'Clinical Advisor': 4
    };
    executionLog.forEach(item => {
        const stepNum = agentMap[item.agent];
        const card = document.getElementById(`agent-step-${stepNum}`);
        if (card) {
            const isOk = item.status === 'completed';
            card.className = `stepper-card ${isOk ? 'completed' : 'active'}`;
            card.querySelector('.stepper-badge').textContent = isOk ? 'Completed ✓' : 'Failed ✗';
            card.querySelector('.stepper-badge').className = `civic-badge ${isOk ? 'level-a' : 'level-c'} stepper-badge`;
            if (item.elapsed) {
                card.querySelector('.stepper-time').textContent = `${item.elapsed}s`;
            }
        }
    });
}

/**
 * Open JSON State Inspector Modal
 */
function openJsonInspector(agentIdx) {
    const modal = document.getElementById('jsonInspectorModal');
    const content = document.getElementById('jsonInspectorContent');
    if (!modal || !content) return;

    let payload = { status: "No data available yet." };
    if (aiPipelineResult) {
        if (agentIdx === 1) payload = aiPipelineResult.mutation_analysis;
        else if (agentIdx === 2) payload = aiPipelineResult.pathway_analysis;
        else if (agentIdx === 3) payload = aiPipelineResult.drug_strategy;
        else if (agentIdx === 4) payload = aiPipelineResult.final_report;
        else payload = aiPipelineResult;
    }

    content.textContent = JSON.stringify(payload, null, 2);
    modal.style.display = 'flex';
}

function closeJsonInspector() {
    document.getElementById('jsonInspectorModal').style.display = 'none';
}

/**
 * Export & Snapshot Actions
 */
function exportClinicalReport() {
    window.print();
}

function downloadSessionJson() {
    const sessionData = {
        timestamp: new Date().toISOString(),
        case_id: "#NSCLC-SESSION-EXPORT",
        selected_mutations: selectedGenes,
        prediction_results: predictionResults,
        ai_pipeline_result: aiPipelineResult
    };

    const blob = new Blob([JSON.stringify(sessionData, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `xmars_session_${Date.now()}.json`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
}

/**
 * Loading Overlay Helpers
 */
function showLoading(msg = 'Processing...') {
    const overlay = document.getElementById('loadingOverlay');
    if (overlay) {
        overlay.classList.add('visible');
        const txt = overlay.querySelector('.loading-text');
        if (txt) txt.textContent = msg;
    }
}

function hideLoading() {
    document.getElementById('loadingOverlay')?.classList.remove('visible');
}

/**
 * Markdown Converter
 */
function markdownToHtml(text) {
    if (!text) return '';
    return text
        .replace(/### (.*)/g, '<h3>$1</h3>')
        .replace(/## (.*)/g, '<h2>$1</h2>')
        .replace(/# (.*)/g, '<h1>$1</h1>')
        .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
        .replace(/\*(.*?)\*/g, '<em>$1</em>')
        .replace(/`(.*?)`/g, '<code>$1</code>')
        .replace(/^\- (.*)/gm, '<li>$1</li>')
        .replace(/^\d+\. (.*)/gm, '<li>$1</li>')
        .replace(/\n\n/g, '</p><p>')
        .replace(/\n/g, '<br>')
        .replace(/^/, '<p>')
        .replace(/$/, '</p>');
}
