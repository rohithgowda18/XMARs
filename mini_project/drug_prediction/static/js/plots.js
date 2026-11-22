/**
 * ═══════════════════════════════════════════════════════════════
 * plots.js — Interactive Precision Oncology Visualizations
 * Inspired by shinyDeepDR (Waterfall) & CellHit (Diverging SHAP)
 * ═══════════════════════════════════════════════════════════════
 */

// Global registry of current evaluated drugs for lookup
let currentDrugCatalog = [];
let currentWaterfallSlice = 10; // Default to Top 10 Actionable Therapies

/**
 * Switcher for Waterfall View Slices (Top 10, Top 25, or All 224)
 */
function setWaterfallView(slice) {
    currentWaterfallSlice = slice;
    document.querySelectorAll('#waterfallViewToggle .cat-btn').forEach(b => b.classList.remove('active'));
    if (slice === 10) document.getElementById('btn-wf-10')?.classList.add('active');
    else if (slice === 25) document.getElementById('btn-wf-25')?.classList.add('active');
    else if (slice === 'all') document.getElementById('btn-wf-all')?.classList.add('active');

    if (currentDrugCatalog && currentDrugCatalog.length > 0) {
        drawWaterfall(currentDrugCatalog, 'waterfallPlotContainer', currentWaterfallSlice);
    }
}

/**
 * 1. shinyDeepDR-Style Plotly Drug Sensitivity Waterfall Plot
 * Entry point to render candidate drugs ranked by sensitivity score.
 */
function renderWaterfallPlot(drugs, containerId = 'waterfallPlotContainer') {
    if (!drugs || drugs.length === 0) {
        const container = document.getElementById(containerId);
        if (container) {
            container.innerHTML = '<div style="text-align:center;padding:60px;color:var(--text-muted)">No drug predictions available to plot.</div>';
        }
        return;
    }

    currentDrugCatalog = drugs;
    drawWaterfall(drugs, containerId, currentWaterfallSlice);
}

/**
 * Internal rendering engine for Waterfall Plot with dynamic slicing & crisp bar widths
 */
function drawWaterfall(drugs, containerId = 'waterfallPlotContainer', slice = 10) {
    const container = document.getElementById(containerId);
    if (!container) return;

    // Sort drugs by predicted sensitivity descending
    const sorted = [...drugs].sort((a, b) => (b.sensitivity_score || 0) - (a.sensitivity_score || 0));

    // Determine slice subset
    const displayList = slice === 'all' ? sorted : sorted.slice(0, slice);
    const count = displayList.length;

    // Update subtitle if element exists
    const subtitle = document.getElementById('waterfallSubtitle');
    if (subtitle) {
        if (slice === 10) {
            subtitle.textContent = `Showing Top 10 Actionable Therapies — Clinical Priority View (Click any bar to inspect compound details)`;
        } else if (slice === 25) {
            subtitle.textContent = `Showing Top 25 Extended Candidates (Click any bar to inspect compound details)`;
        } else {
            subtitle.textContent = `Showing Full Screen: All ${sorted.length} Evaluated Compounds (Interactive zoom & pan enabled)`;
        }
    }

    const names = displayList.map(d => d.drug_name || d.name);
    const scores = displayList.map(d => Math.round((d.sensitivity_score || 0) * 100));

    // Semantic color assignment
    const colors = scores.map(s => {
        if (s >= 70) return '#10b981'; // Emerald Sensitive (≥70%)
        if (s >= 52) return '#84cc16'; // Moderate
        if (s >= 48) return '#eab308'; // Intermediate
        return '#ef4444';              // Resistant (<48%)
    });

    const isFocusedView = slice === 10 || slice === 25;

    // Check if Plotly library is loaded
    if (typeof Plotly !== 'undefined') {
        const trace = {
            x: names,
            y: scores,
            type: 'bar',
            marker: {
                color: colors,
                line: { color: 'rgba(255,255,255,0.15)', width: 1 }
            },
            // For focused views, show crisp percentage text directly above the wide bars!
            text: isFocusedView ? scores.map(s => `<b>${s}%</b>`) : undefined,
            textposition: isFocusedView ? 'outside' : 'none',
            textfont: {
                color: '#f1f5f9',
                size: slice === 10 ? 12 : 10,
                family: 'Inter, sans-serif'
            },
            cliponaxis: false,
            hoverinfo: 'text',
            hovertext: displayList.map(d => `
<b>${d.drug_name || d.name}</b>
• Primary Target: ${d.targets || d.target || 'N/A'}
• Pathway: ${d.pathway || 'General'}
• Sensitivity: ${Math.round((d.sensitivity_score || 0) * 100)}%
• Resistance: ${Math.round((d.resistance_score || 0) * 100)}%
• Status: ${(d.sensitivity_score || 0) >= 0.7 ? 'Sensitive (Targeted)' : (d.sensitivity_score || 0) >= 0.48 ? 'Intermediate' : 'Resistant'}
<i>👉 Click bar to inspect pharmacology & clinical evidence</i>
            `)
        };

        const layout = {
            paper_bgcolor: 'transparent',
            plot_bgcolor: 'transparent',
            margin: { t: 36, r: 24, l: 54, b: slice === 10 ? 90 : 110 },
            bargap: slice === 10 ? 0.35 : slice === 25 ? 0.25 : 0.1,
            xaxis: {
                title: {
                    text: slice === 'all'
                        ? `All Evaluated Oncology Compounds (Total: ${sorted.length})`
                        : `Top ${count} Candidate Therapies (Ranked by Predicted Sensitivity)`,
                    font: { color: '#94a3b8', size: 12 }
                },
                tickangle: slice === 10 ? -28 : -45,
                tickfont: {
                    color: '#e2e8f0',
                    size: slice === 10 ? 11 : slice === 25 ? 9.5 : 8
                },
                showgrid: false,
                zeroline: false
            },
            yaxis: {
                title: { text: 'Predicted Sensitivity (%)', font: { color: '#94a3b8', size: 12 } },
                range: [0, isFocusedView ? 114 : 100],
                tickfont: { color: '#94a3b8', size: 10 },
                gridcolor: 'rgba(255,255,255,0.06)'
            },
            shapes: [
                {
                    type: 'line',
                    x0: 0,
                    x1: 1,
                    xref: 'paper',
                    y0: 50,
                    y1: 50,
                    line: {
                        color: 'rgba(234, 179, 8, 0.45)',
                        width: 1.5,
                        dash: 'dash'
                    }
                }
            ],
            annotations: [
                {
                    xref: 'paper',
                    yref: 'y',
                    x: 1.0,
                    y: 52,
                    xanchor: 'right',
                    text: 'Efficacy Threshold (50%)',
                    font: { size: 9, color: 'rgba(234, 179, 8, 0.7)' },
                    showarrow: false
                }
            ]
        };

        const config = { responsive: true, displayModeBar: slice === 'all' };

        Plotly.newPlot(container, [trace], layout, config).then(() => {
            container.on('plotly_click', data => {
                if (data.points && data.points.length > 0) {
                    const drugName = data.points[0].x;
                    if (typeof openDrugDrawer === 'function') {
                        openDrugDrawer(drugName);
                    }
                }
            });
        }).catch(err => {
            console.warn('Plotly rendering error, falling back to SVG:', err);
            renderFallbackWaterfallSVG(container, displayList);
        });
    } else {
        // Fallback SVG rendering if offline
        renderFallbackWaterfallSVG(container, displayList);
    }
}

/**
 * Fallback SVG waterfall bar chart when Plotly CDN is unavailable
 */
function renderFallbackWaterfallSVG(container, drugs) {
    const width = container.clientWidth || 800;
    const height = 400;
    const padding = { top: 40, right: 24, bottom: 80, left: 54 };
    const chartW = width - padding.left - padding.right;
    const chartH = height - padding.top - padding.bottom;

    const slotW = chartW / drugs.length;
    const barW = Math.min(Math.max(slotW * 0.65, 4), 54);

    let barsSvg = '';
    drugs.forEach((d, i) => {
        const sens = Math.round((d.sensitivity_score || 0) * 100);
        const barH = (sens / 100) * chartH;
        const x = padding.left + i * slotW + (slotW - barW) / 2;
        const y = padding.top + (chartH - barH);
        const color = sens >= 70 ? '#10b981' : sens >= 50 ? '#eab308' : '#ef4444';
        const name = d.drug_name || d.name;

        barsSvg += `
            <rect x="${x}" y="${y}" width="${barW}" height="${barH}" fill="${color}" rx="3" style="cursor:pointer;" onclick="openDrugDrawer('${name}')">
                <title>${name}: ${sens}% Sensitivity (${d.targets || 'Target N/A'})</title>
            </rect>
            ${drugs.length <= 25 ? `<text x="${x + barW / 2}" y="${y - 6}" fill="#f1f5f9" font-size="11" font-weight="bold" text-anchor="middle">${sens}%</text>` : ''}
            ${drugs.length <= 15 ? `<text x="${x + barW / 2}" y="${padding.top + chartH + 16}" fill="#94a3b8" font-size="10" text-anchor="end" transform="rotate(-35, ${x + barW / 2}, ${padding.top + chartH + 16})">${name}</text>` : ''}
        `;
    });

    container.innerHTML = `
        <svg width="100%" height="${height}" viewBox="0 0 ${width} ${height}">
            <line x1="${padding.left}" y1="${padding.top + chartH}" x2="${width - padding.right}" y2="${padding.top + chartH}" stroke="rgba(255,255,255,0.2)" />
            <line x1="${padding.left}" y1="${padding.top + chartH / 2}" x2="${width - padding.right}" y2="${padding.top + chartH / 2}" stroke="rgba(234,179,8,0.3)" stroke-dasharray="4" />
            <text x="${padding.left - 10}" y="${padding.top + chartH / 2 + 4}" fill="#94a3b8" font-size="10" text-anchor="end">50%</text>
            ${barsSvg}
        </svg>
    `;
}

/**
 * 2. CellHit-Style Diverging SHAP Feature Importance Plot
 * Displays signed feature contributions (positive = resistance/driver, negative = sensitivity/passenger)
 */
function renderDivergingSHAP(waterfallData, containerId = 'shapDivergingPlot') {
    const container = document.getElementById(containerId);
    if (!container) return;

    if (!waterfallData || !waterfallData.labels || waterfallData.labels.length === 0) {
        container.innerHTML = '<div style="text-align:center;padding:40px;color:var(--text-muted)">Run AI Agent Analysis to generate SHAP attribution vectors.</div>';
        return;
    }

    const labels = waterfallData.labels.map(l => l.replace('ohe_', '').replace(/_/g, ' '));
    const values = waterfallData.values;
    const colors = values.map(v => v >= 0 ? '#f43f5e' : '#06b6d4');

    if (typeof Plotly !== 'undefined') {
        const trace = {
            y: labels,
            x: values,
            type: 'bar',
            orientation: 'h',
            marker: {
                color: colors,
                line: { color: 'rgba(255,255,255,0.15)', width: 0.5 }
            },
            hoverinfo: 'text',
            text: values.map((v, i) => `${labels[i]}: ${v > 0 ? '+' : ''}${v.toFixed(4)}`)
        };

        const maxAbs = Math.max(...values.map(Math.abs), 0.1);

        const layout = {
            paper_bgcolor: 'transparent',
            plot_bgcolor: 'transparent',
            margin: { t: 20, r: 30, l: 150, b: 40 },
            xaxis: {
                title: { text: 'Shapley Contribution Value (ϕ)', font: { color: '#94a3b8', size: 11 } },
                range: [-maxAbs * 1.15, maxAbs * 1.15],
                tickfont: { color: '#94a3b8' },
                gridcolor: 'rgba(255,255,255,0.06)',
                zerolinecolor: 'rgba(255,255,255,0.3)',
                zerolinewidth: 2
            },
            yaxis: {
                tickfont: { color: '#f1f5f9', size: 11 },
                autorange: 'reversed'
            }
        };

        Plotly.newPlot(container, [trace], layout, { responsive: true, displayModeBar: false }).catch(err => {
            console.warn('Plotly SHAP error, falling back to HTML:', err);
            renderFallbackSHAP(container, labels, values);
        });
    } else {
        renderFallbackSHAP(container, labels, values);
    }
}

function renderFallbackSHAP(container, labels, values) {
    let html = '<div style="display:flex;flex-direction:column;gap:8px;padding:12px;">';
    const maxAbs = Math.max(...values.map(Math.abs), 0.1);
    labels.forEach((lbl, i) => {
        const v = values[i];
        const pct = (Math.abs(v) / maxAbs) * 50;
        const isPos = v >= 0;
        const color = isPos ? '#f43f5e' : '#06b6d4';
        html += `
            <div style="display:flex;align-items:center;font-size:0.8rem;gap:12px;">
                <div style="width:140px;text-align:right;color:var(--text-secondary);">${lbl}</div>
                <div style="flex:1;display:flex;align-items:center;height:18px;background:rgba(255,255,255,0.03);position:relative;">
                    <div style="position:absolute;left:50%;top:0;bottom:0;width:1px;background:rgba(255,255,255,0.2);"></div>
                    <div style="position:absolute;${isPos ? 'left:50%' : `right:50%`};height:12px;width:${pct}%;background:${color};border-radius:2px;"></div>
                </div>
                <div style="width:60px;font-family:monospace;color:${color};font-weight:600;">${v > 0 ? '+' : ''}${v.toFixed(3)}</div>
            </div>
        `;
    });
    html += '</div>';
    container.innerHTML = html;
}

// Signaling View State
let currentSignalingViewMode = 'disrupted'; // 'disrupted' | 'all'
let currentSignalingData = null;

/**
 * Switch Signaling View Mode (Disrupted Circuits vs Full Canonical Network)
 */
function setSignalingViewMode(mode) {
    currentSignalingViewMode = mode;
    const btnDisrupted = document.getElementById('btnSignalingViewDisrupted');
    const btnAll = document.getElementById('btnSignalingViewAll');
    if (btnDisrupted && btnAll) {
        if (mode === 'disrupted') {
            btnDisrupted.classList.add('active');
            btnDisrupted.style.background = 'var(--primary)';
            btnDisrupted.style.color = '#fff';
            btnAll.classList.remove('active');
            btnAll.style.background = 'transparent';
            btnAll.style.color = 'var(--text-secondary)';
        } else {
            btnAll.classList.add('active');
            btnAll.style.background = 'var(--primary)';
            btnAll.style.color = '#fff';
            btnDisrupted.classList.remove('active');
            btnDisrupted.style.background = 'transparent';
            btnDisrupted.style.color = 'var(--text-secondary)';
        }
    }
    if (currentSignalingData) {
        renderSignalingPathwayDiagram(currentSignalingData);
    }
}

/**
 * Close Interactive Molecular Node Inspector
 */
function closeSignalingNodeInspector() {
    const inspector = document.getElementById('pathwayNodeInspector');
    if (inspector) inspector.style.display = 'none';
}

/**
 * 3. Interactive Oncogenic Signaling Pathway & Bypass Resistance Network
 * Topologically maps Extracellular Receptors -> Secondary Messengers -> Nuclear Effectors
 * Dynamically highlights mutated drivers, drug target blockades, and constitutive bypass escape routes.
 */
function renderSignalingPathwayDiagram(data, containerId = 'pathwayDiagramContainer') {
    const container = document.getElementById(containerId);
    if (!container) return;
    if (data) currentSignalingData = data;

    // 1. Extract mutated genes and analyses from Agent 1 / Agent Pipeline
    const geneAnalysesMap = {};
    const mutatedGenes = new Set();
    const geneAnalyses = data.mutation_analysis?.gene_analyses || [];
    geneAnalyses.forEach(ga => {
        const g = String(ga.gene).toUpperCase();
        mutatedGenes.add(g);
        geneAnalysesMap[g] = ga;
    });

    // Fallback mutation extraction if gene_analyses is not populated
    const mutations = data.mutations_analyzed || (data.mutation_summary?.mutations ? data.mutation_summary.mutations.map(m => m.gene) : Object.keys(window.selectedGenes || {}));
    mutations.forEach(g => {
        const geneUpper = String(g).toUpperCase();
        mutatedGenes.add(geneUpper);
        if (!geneAnalysesMap[geneUpper]) {
            const vaf = (window.selectedGenes && window.selectedGenes[geneUpper]) || 0.45;
            geneAnalysesMap[geneUpper] = { gene: geneUpper, vaf: vaf, classification: 'Pathogenic Alteration', avg_shap_importance: 0.045 };
        }
    });

    // 2. Extract affected pathways from Agent 2 (Pathway Specialist)
    const affectedPathways = data.affected_pathways || data.pathway_analysis?.affected_pathways || [];
    const pathwayScoreMap = {};
    const compromisedTargets = new Set();
    affectedPathways.forEach(p => {
        const pwName = String(p.name || p.pathway || '').toUpperCase();
        pathwayScoreMap[pwName] = {
            name: p.name || p.pathway,
            score: p.activation_score || 0,
            driver_mutations: p.driver_mutations || 0,
            compromised_targets: p.compromised_drug_targets || []
        };
        (p.compromised_drug_targets || []).forEach(t => compromisedTargets.add(String(t).toUpperCase()));
    });

    // 3. Extract top recommended drug and candidate targets from Agent 3 (Drug Strategist)
    const drugs = data.drug_predictions || data.drug_strategy?.top_10 || data.drug_strategy?.ranked_drugs || [];
    const topDrug = drugs.length > 0 ? drugs[0] : null;
    const topDrugName = topDrug ? (topDrug.drug_name || topDrug.name) : 'Osimertinib';
    const topDrugTarget = topDrug ? String(topDrug.targets || topDrug.target || 'EGFR').toUpperCase() : 'EGFR';
    const topDrugScore = topDrug ? Math.round((topDrug.sensitivity_score || 0) * 100) : 78;

    // 4. Identify bypass resistance from Drug Strategist evidence & knowledge base
    let bypassDetected = false;
    let bypassReason = '';

    // Check drug prediction sources for bypass resistance
    drugs.forEach(d => {
        if (d.sources && d.sources.includes('bypass_resistance')) {
            bypassDetected = true;
            if (d.reasoning && d.reasoning.length > 0) {
                bypassReason = d.reasoning.find(r => r.toLowerCase().includes('bypass')) || d.reasoning[0];
            }
        }
    });

    // Cross-check standard bypass circuits (EGFR TKI bypassed by MET, KRAS, PIK3CA, PTEN, NF1)
    const hasEGFR = mutatedGenes.has('EGFR');
    const hasMET = mutatedGenes.has('MET');
    const hasKRAS = mutatedGenes.has('KRAS') || mutatedGenes.has('BRAF');
    const hasPI3K = mutatedGenes.has('PIK3CA');
    const hasPTEN = mutatedGenes.has('PTEN');

    if (!bypassDetected) {
        if (hasEGFR && hasMET) {
            bypassDetected = true;
            bypassReason = 'MET amplification bypasses EGFR inhibition via alternative RTK transactivation';
        } else if (hasEGFR && hasKRAS) {
            bypassDetected = true;
            bypassReason = 'Downstream KRAS mutation confers constitutive MAPK drive bypassing upstream EGFR blockade';
        } else if (hasEGFR && (hasPI3K || hasPTEN)) {
            bypassDetected = true;
            bypassReason = 'PI3K/PTEN aberration sustains intracellular survival signaling independent of EGFR';
        }
    }

    // 5. Curated Node Topology (Topological cascade: Membrane -> Transduction -> Cascade -> Nuclear)
    const allNodes = [
        // Layer 0: Extracellular Ligand / Membrane Receptors
        { id: 'EGFR', label: 'EGFR / HER2', type: 'receptor', x: 180, y: 80, role: 'RTK Receptor', pathways: ['EGFR_SIGNALING'] },
        { id: 'MET', label: 'c-MET', type: 'receptor', x: 450, y: 80, role: 'Bypass RTK', pathways: ['EGFR_SIGNALING'] },
        { id: 'ALK', label: 'ALK / RET', type: 'receptor', x: 720, y: 80, role: 'Translocation RTK', pathways: ['EGFR_SIGNALING'] },

        // Layer 1: Intracellular Adaptors & Hubs
        { id: 'KRAS', label: 'KRAS', type: 'adaptor', x: 230, y: 190, role: 'MAPK GTPase Hub', pathways: ['RAS_PATHWAY', 'MAPK_ERK', 'EGFR_SIGNALING'] },
        { id: 'PIK3CA', label: 'PI3K (p110α)', type: 'adaptor', x: 480, y: 190, role: 'Survival Hub', pathways: ['PI3K_AKT_MTOR', 'EGFR_SIGNALING'] },
        { id: 'PTEN', label: 'PTEN', type: 'tumor_suppressor', x: 700, y: 190, role: 'Lipid Brake (Suppressor)', pathways: ['PI3K_AKT_MTOR', 'EGFR_SIGNALING'] },

        // Layer 2: Intermediate Kinase Cascades
        { id: 'BRAF', label: 'BRAF / MEK1', type: 'cascade', x: 230, y: 295, role: 'Mitogenic Cascade', pathways: ['MAPK_ERK', 'EGFR_SIGNALING'] },
        { id: 'AKT', label: 'AKT / mTOR', type: 'cascade', x: 480, y: 295, role: 'Survival Effector', pathways: ['PI3K_AKT_MTOR'] },
        { id: 'TP53', label: 'p53', type: 'tumor_suppressor', x: 720, y: 295, role: 'Genome Guardian', pathways: ['TP53_APOPTOSIS', 'EGFR_SIGNALING'] },

        // Layer 3: Cellular Phenotypes & Therapeutic Endpoints
        { id: 'PROLIFERATION', label: 'Cell Proliferation (MAPK)', type: 'phenotype', x: 230, y: 400, role: 'Mitogenic Drive' },
        { id: 'SURVIVAL', label: 'Anti-Apoptotic Survival', type: 'phenotype', x: 480, y: 400, role: 'Tumor Viability' },
        { id: 'RESISTANCE', label: 'Therapeutic Bypass Escape', type: 'phenotype', x: 720, y: 400, role: 'TKI Drug Resistance' }
    ];

    // Canonical signaling connections
    const allEdges = [
        { from: 'EGFR', to: 'KRAS', type: 'activate', role: 'Canonical MAPK drive' },
        { from: 'EGFR', to: 'PIK3CA', type: 'activate', role: 'Canonical PI3K survival' },
        { from: 'MET', to: 'PIK3CA', type: 'bypass', role: 'Bypass survival cross-talk' },
        { from: 'MET', to: 'KRAS', type: 'bypass', role: 'Bypass MAPK cross-talk' },
        { from: 'ALK', to: 'KRAS', type: 'activate', role: 'Translocation RTK activation' },
        { from: 'ALK', to: 'PIK3CA', type: 'activate', role: 'Alternative RTK survival' },
        { from: 'KRAS', to: 'BRAF', type: 'activate', role: 'Cascade transmission' },
        { from: 'BRAF', to: 'PROLIFERATION', type: 'activate', role: 'Transcriptional growth' },
        { from: 'PIK3CA', to: 'AKT', type: 'activate', role: 'PIP3 mediated phosphorylation' },
        { from: 'PTEN', to: 'AKT', type: 'inhibit', role: 'Inhibitory lipid brake' },
        { from: 'AKT', to: 'SURVIVAL', type: 'activate', role: 'Apoptosis suppression' },
        { from: 'TP53', to: 'SURVIVAL', type: 'inhibit', role: 'Apoptotic checkpoint' },
        { from: 'KRAS', to: 'RESISTANCE', type: 'bypass', role: 'Downstream escape from EGFR inhibition' },
        { from: 'AKT', to: 'RESISTANCE', type: 'bypass', role: 'Sustained survival escape route' }
    ];

    // Determine perturbed circuit elements
    const isNodePerturbed = (n) => {
        if (mutatedGenes.has(n.id)) return true;
        if (n.id === topDrugTarget) return true;
        if (n.id === 'RESISTANCE' && bypassDetected) return true;
        if (n.id === 'PROLIFERATION' && (mutatedGenes.has('KRAS') || mutatedGenes.has('BRAF') || mutatedGenes.has('EGFR'))) return true;
        if (n.id === 'SURVIVAL' && (mutatedGenes.has('PIK3CA') || mutatedGenes.has('PTEN') || mutatedGenes.has('AKT') || mutatedGenes.has('TP53') || mutatedGenes.has('MET'))) return true;
        if (n.pathways && n.pathways.some(pw => pathwayScoreMap[pw] && pathwayScoreMap[pw].score > 0)) return true;
        return false;
    };

    // Filter nodes for 'disrupted' view mode
    let displayNodes = allNodes;
    if (currentSignalingViewMode === 'disrupted' && mutatedGenes.size > 0) {
        displayNodes = allNodes.map(n => ({
            ...n,
            isPerturbed: isNodePerturbed(n)
        }));
    } else {
        displayNodes = allNodes.map(n => ({
            ...n,
            isPerturbed: true
        }));
    }

    const nodeMap = {};
    displayNodes.forEach(n => { nodeMap[n.id] = n; });

    // Edge rendering
    let svgEdges = '';
    allEdges.forEach(e => {
        const source = nodeMap[e.from];
        const target = nodeMap[e.to];
        if (!source || !target) return;

        const isSourcePerturbed = isNodePerturbed(source);
        const isTargetPerturbed = isNodePerturbed(target);
        const isBypass = e.type === 'bypass' && bypassDetected;
        const isEdgeActive = isBypass || (isSourcePerturbed && isTargetPerturbed);

        // Opacity and styling depending on filter view
        if (currentSignalingViewMode === 'disrupted' && mutatedGenes.size > 0 && !isEdgeActive && !isBypass) {
            // Keep subtle dim representation so topology remains interpretable
            return;
        }

        let strokeColor = '#38bdf8';
        let strokeW = 2;
        let strokeDash = 'none';
        let opacity = 0.55;

        if (isBypass) {
            strokeColor = '#eab308';
            strokeW = 3.2;
            strokeDash = '6,4';
            opacity = 0.95;
        } else if (e.type === 'inhibit') {
            strokeColor = '#94a3b8';
            strokeW = 2;
            strokeDash = '4,4';
            opacity = 0.7;
        } else if (isEdgeActive && mutatedGenes.size > 0) {
            strokeColor = '#38bdf8';
            strokeW = 2.5;
            opacity = 0.85;
        } else {
            strokeColor = '#475569';
            strokeW = 1.5;
            opacity = 0.35;
        }

        // Curved quadratic Bezier line
        const midX = (source.x + target.x) / 2 + (e.from === 'MET' && e.to === 'KRAS' ? -35 : 0);
        const midY = (source.y + target.y) / 2;

        svgEdges += `
            <path d="M ${source.x} ${source.y} Q ${midX} ${midY} ${target.x} ${target.y}" 
                  fill="none" stroke="${strokeColor}" stroke-width="${strokeW}" stroke-dasharray="${strokeDash}" opacity="${opacity}">
                ${isBypass ? '<animate attributeName="stroke-dashoffset" values="40;0" dur="1.2s" repeatCount="indefinite" />' : ''}
            </path>
        `;
    });

    // Node rendering
    let svgNodes = '';
    displayNodes.forEach(n => {
        const isMutated = mutatedGenes.has(n.id);
        const isInhibited = n.id === topDrugTarget;
        const ga = geneAnalysesMap[n.id];
        const isBypassHub = (n.id === 'MET' || n.id === 'KRAS') && bypassDetected;

        let fillColor = 'rgba(30, 41, 59, 0.85)';
        let strokeColor = '#475569';
        let glow = '';
        let subtitleText = n.role;
        let subtitleColor = '#94a3b8';

        if (isMutated) {
            fillColor = 'rgba(239, 68, 68, 0.22)';
            strokeColor = '#ef4444';
            glow = 'filter="drop-shadow(0 0 8px rgba(239, 68, 68, 0.75))"';
            subtitleText = ga && ga.vaf ? `● MUTATED (VAF: ${(ga.vaf).toFixed(2)})` : '● MUTATED DRIVER';
            subtitleColor = '#fca5a5';
        } else if (isInhibited) {
            fillColor = 'rgba(16, 185, 129, 0.22)';
            strokeColor = '#10b981';
            glow = 'filter="drop-shadow(0 0 8px rgba(16, 185, 129, 0.7))"';
            subtitleText = `⚡ TARGETED (${topDrugName})`;
            subtitleColor = '#6ee7b7';
        } else if (n.type === 'phenotype') {
            if (n.id === 'RESISTANCE') {
                fillColor = bypassDetected ? 'rgba(234, 179, 8, 0.22)' : 'rgba(15, 23, 42, 0.9)';
                strokeColor = bypassDetected ? '#eab308' : '#334155';
                subtitleColor = bypassDetected ? '#fef08a' : '#64748b';
                subtitleText = bypassDetected ? '⚠️ THERAPEUTIC ESCAPE' : 'Intact Target Sensitivity';
                if (bypassDetected) glow = 'filter="drop-shadow(0 0 8px rgba(234, 179, 8, 0.75))"';
            } else {
                fillColor = 'rgba(15, 23, 42, 0.9)';
                strokeColor = isNodePerturbed(n) ? '#38bdf8' : '#334155';
                subtitleColor = isNodePerturbed(n) ? '#bae6fd' : '#64748b';
            }
        } else if (isBypassHub) {
            fillColor = 'rgba(234, 179, 8, 0.15)';
            strokeColor = '#eab308';
            subtitleColor = '#fef08a';
            subtitleText = '⚠️ BYPASS CONDUIT';
        }

        const width = n.type === 'phenotype' ? 200 : 134;
        const height = 48;
        const rx = n.type === 'phenotype' ? 8 : 24;

        svgNodes += `
            <g transform="translate(${n.x - width / 2}, ${n.y - height / 2})" ${glow} style="cursor:pointer;" onclick="inspectSignalingNode('${n.id}')">
                <rect width="${width}" height="${height}" rx="${rx}" fill="${fillColor}" stroke="${strokeColor}" stroke-width="2" />
                <text x="${width / 2}" y="22" fill="#ffffff" font-size="12" font-weight="700" text-anchor="middle" font-family="Inter, sans-serif">
                    ${n.label}
                </text>
                <text x="${width / 2}" y="36" fill="${subtitleColor}" font-size="8.5" font-weight="500" text-anchor="middle" font-family="Inter, sans-serif">
                    ${subtitleText}
                </text>
                ${isInhibited ? `
                    <circle cx="16" cy="16" r="8" fill="#10b981" />
                    <text x="16" y="20" fill="#000" font-size="9" font-weight="bold" text-anchor="middle">Rx</text>
                ` : ''}
            </g>
        `;
    });

    // Dynamic Clinical Header Status Banner
    let statusBanner = '';
    if (mutatedGenes.size === 0) {
        statusBanner = `
            <div style="position:absolute; top:12px; left:16px; background:rgba(56, 189, 248, 0.12); border:1px solid rgba(56, 189, 248, 0.35); padding:6px 14px; border-radius:6px; color:#bae6fd; font-size:0.78rem; display:flex; align-items:center; gap:8px;">
                <span>ℹ️</span> <strong>Canonical Basal Network:</strong> No genomic driver alterations detected in current specimen. Baseline circuits intact.
            </div>
        `;
    } else if (bypassDetected) {
        statusBanner = `
            <div style="position:absolute; top:12px; left:16px; background:rgba(234, 179, 8, 0.15); border:1px solid rgba(234, 179, 8, 0.45); padding:6px 14px; border-radius:6px; color:#fef08a; font-size:0.78rem; display:flex; align-items:center; gap:8px;">
                <span>⚠️</span> <strong>Critical Bypass Circuit Activated:</strong> ${bypassReason || 'Alternative kinase signaling circumventing primary target inhibition.'}
            </div>
        `;
    } else {
        statusBanner = `
            <div style="position:absolute; top:12px; left:16px; background:rgba(16, 185, 129, 0.15); border:1px solid rgba(16, 185, 129, 0.35); padding:6px 14px; border-radius:6px; color:#a7f3d0; font-size:0.78rem; display:flex; align-items:center; gap:8px;">
                <span>🛡️</span> <strong>Linear Target Control:</strong> Primary oncogenic drive inhibited by ${topDrugName} (${topDrugScore}% predicted sensitivity).
            </div>
        `;
    }

    container.innerHTML = `
        ${statusBanner}
        <div style="position:absolute; top:14px; right:16px; color:#64748b; font-size:0.75rem; font-family:Inter, sans-serif;">
            Click any gene or phenotype node to inspect evidence & therapies
        </div>
        <svg width="100%" height="460" viewBox="0 0 900 460" style="display:block; margin:0 auto;">
            <!-- Membrane reference line -->
            <line x1="50" y1="125" x2="850" y2="125" stroke="rgba(255,255,255,0.08)" stroke-dasharray="4,4" />
            <text x="60" y="120" fill="#475569" font-size="9.5" font-family="Inter, sans-serif">CELL PLASMA MEMBRANE</text>

            <!-- Nuclear boundary line -->
            <line x1="50" y1="355" x2="850" y2="355" stroke="rgba(255,255,255,0.08)" stroke-dasharray="4,4" />
            <text x="60" y="350" fill="#475569" font-size="9.5" font-family="Inter, sans-serif">NUCLEAR TRANSLOCATION & TRANSCRIPTION</text>

            <!-- Rendered Edges & Nodes -->
            ${svgEdges}
            ${svgNodes}
        </svg>
    `;
}

/**
 * Interactive Inspection Card on Node Click
 * Surfaces empirical VCF findings, SHAP attribution values, pathway disruption scores, and known drugs.
 */
function inspectSignalingNode(nodeId) {
    const inspector = document.getElementById('pathwayNodeInspector');
    if (!inspector) return;

    const data = currentSignalingData || {};
    const geneUpper = String(nodeId).toUpperCase();

    // Curated Pharmacogenomic Knowledge Map (Verified against project data/processed/03_compounds_cleaned.csv)
    const KNOWLEDGE_BASE_DRUGS = {
        'EGFR': [
            { name: 'Osimertinib', target: 'EGFR T790M/L858R', status: 'FDA Approved (1st Line NSCLC)' },
            { name: 'Erlotinib', target: 'EGFR (Exon 19 del / L858R)', status: 'FDA Approved (1st Gen TKI)' },
            { name: 'Afatinib', target: 'EGFR / HER2 (Pan-ErbB)', status: 'FDA Approved (2nd Gen TKI)' }
        ],
        'MET': [
            { name: 'Capmatinib', target: 'c-MET (Exon 14 / Amp)', status: 'FDA Approved (NSCLC METex14)' },
            { name: 'Tepotinib', target: 'c-MET Kinase', status: 'FDA Approved (NSCLC METex14)' },
            { name: 'Crizotinib', target: 'MET / ALK / ROS1', status: 'FDA Approved (Multi-Kinase TKI)' }
        ],
        'KRAS': [
            { name: 'Sotorasib', target: 'KRAS G12C (Switch II)', status: 'FDA Approved (NSCLC KRAS G12C)' },
            { name: 'Adagrasib', target: 'KRAS G12C', status: 'FDA Approved (NSCLC KRAS G12C)' }
        ],
        'BRAF': [
            { name: 'Dabrafenib', target: 'BRAF V600E', status: 'FDA Approved (NSCLC BRAF V600E + Trametinib)' },
            { name: 'Encorafenib', target: 'BRAF V600E', status: 'FDA Approved (BRAF Inhibitor)' }
        ],
        'PIK3CA': [
            { name: 'Alpelisib', target: 'PI3K p110α', status: 'FDA Approved (PI3K Inhibitor)' },
            { name: 'Copanlisib', target: 'Pan-PI3K', status: 'FDA Approved' }
        ],
        'ALK': [
            { name: 'Alectinib', target: 'ALK Fusion Kinase', status: 'FDA Approved (1st Line ALK+ NSCLC)' },
            { name: 'Brigatinib', target: 'ALK / EGFR', status: 'FDA Approved (2nd Gen ALK TKI)' }
        ],
        'PTEN': [
            { name: 'mTOR/AKT Blockade', target: 'PI3K/AKT Pathway', status: 'Clinical Evaluation (PTEN Loss)' }
        ],
        'TP53': [
            { name: 'MDM2 Inhibitors', target: 'p53-MDM2 Axis', status: 'Investigational / Wild-type only' }
        ],
        'AKT': [
            { name: 'Capivasertib', target: 'AKT1/2/3', status: 'FDA Approved (AKT Inhibitor)' }
        ]
    };

    // Extract mutation data for this gene
    const geneAnalyses = data.mutation_analysis?.gene_analyses || [];
    const ga = geneAnalyses.find(g => String(g.gene).toUpperCase() === geneUpper);
    const isMutated = Boolean(ga || (window.selectedGenes && window.selectedGenes[geneUpper]));
    const vaf = ga?.vaf || (window.selectedGenes && window.selectedGenes[geneUpper]) || null;
    const shapVal = ga?.avg_shap_importance || (ga?.shap_features && ga.shap_features[0]?.importance) || null;
    const classification = ga?.classification || (isMutated ? 'Pathogenic Driver Mutation' : 'Wild-Type (Unperturbed)');

    // Extract affected pathways containing this gene
    const affectedPathways = data.affected_pathways || data.pathway_analysis?.affected_pathways || [];
    const matchedPathways = affectedPathways.filter(p => {
        const genes = (p.all_genes || p.genes || []).map(g => String(g).toUpperCase());
        const mutGenes = (p.mutated_genes || []).map(g => String(g.gene || g).toUpperCase());
        return genes.includes(geneUpper) || mutGenes.includes(geneUpper);
    });

    // Associated Drugs from Knowledge Base
    const knownDrugs = KNOWLEDGE_BASE_DRUGS[geneUpper] || [];

    // Top recommended drug relation
    const drugs = data.drug_predictions || data.drug_strategy?.top_10 || [];
    const topDrug = drugs.find(d => {
        const tg = String(d.targets || d.target || '').toUpperCase();
        return tg.includes(geneUpper);
    });

    inspector.style.display = 'block';
    inspector.innerHTML = `
        <div style="display:flex; justify-content:space-between; align-items:flex-start; margin-bottom:12px; border-bottom:1px solid rgba(255,255,255,0.08); padding-bottom:8px;">
            <div>
                <h4 style="margin:0; font-size:1.05rem; color:#ffffff; display:flex; align-items:center; gap:8px;">
                    <span>🧬</span> ${geneUpper} Molecular Node & Circuit Inspector
                    <span class="civic-badge ${isMutated ? 'level-a' : 'level-c'}" style="font-size:0.75rem;">
                        ${isMutated ? 'SOMATIC VARIANT' : 'WILD-TYPE'}
                    </span>
                </h4>
                <div style="font-size:0.8rem; color:var(--text-secondary); margin-top:3px;">
                    Functional Category: <strong>${getNodeCategoryTitle(geneUpper)}</strong> | Canonical Cascade: <strong>${getNodePathwaysString(geneUpper)}</strong>
                </div>
            </div>
            <button onclick="closeSignalingNodeInspector()" style="background:transparent; border:none; color:var(--text-muted); font-size:1.2rem; cursor:pointer; padding:0 4px;">✕</button>
        </div>

        <div style="display:grid; grid-template-columns: repeat(auto-fit, minmax(240px, 1fr)); gap:14px;">
            <!-- Genomic & ML Consensus -->
            <div style="background:rgba(255,255,255,0.03); border:1px solid rgba(255,255,255,0.06); border-radius:6px; padding:12px;">
                <div style="font-size:0.75rem; text-transform:uppercase; color:var(--primary); font-weight:700; margin-bottom:8px;">
                    Genomic & ML Consensus Call
                </div>
                <div style="font-size:0.85rem; color:#f1f5f9; margin-bottom:4px;">
                    Status: <strong>${classification}</strong>
                </div>
                <div style="font-size:0.82rem; color:var(--text-secondary); margin-bottom:4px;">
                    Tumor VAF: <strong>${vaf !== null ? (vaf).toFixed(2) : 'Not Detected (0.00)'}</strong>
                </div>
                <div style="font-size:0.82rem; color:var(--text-secondary); margin-bottom:6px;">
                    SHAP Attribution ($\phi$): <strong>${shapVal !== null ? (shapVal > 0 ? '+' : '') + Number(shapVal).toFixed(4) : 'Baseline'}</strong>
                </div>
                <div style="display:flex; gap:6px; flex-wrap:wrap; margin-top:8px;">
                    <span style="font-size:0.7rem; background:rgba(56,189,248,0.15); color:#7dd3fc; padding:2px 6px; border-radius:3px;">VCF Variant Call</span>
                    <span style="font-size:0.7rem; background:rgba(16,185,129,0.15); color:#6ee7b7; padding:2px 6px; border-radius:3px;">TreeExplainer SHAP</span>
                </div>
            </div>

            <!-- Disrupted Pathway Scores -->
            <div style="background:rgba(255,255,255,0.03); border:1px solid rgba(255,255,255,0.06); border-radius:6px; padding:12px;">
                <div style="font-size:0.75rem; text-transform:uppercase; color:var(--primary); font-weight:700; margin-bottom:8px;">
                    Pathway Disruption Analysis
                </div>
                ${matchedPathways.length > 0 ? matchedPathways.map(p => `
                    <div style="margin-bottom:6px;">
                        <div style="display:flex; justify-content:space-between; font-size:0.82rem;">
                            <span style="color:#ffffff;">${p.name || p.pathway}</span>
                            <span style="color:#38bdf8; font-weight:600;">${Math.round((p.activation_score || 0) * 100)}% Disruption</span>
                        </div>
                        <div style="font-size:0.75rem; color:var(--text-muted);">
                            Drivers: ${p.driver_mutations || 0} | Compromised Targets: ${(p.compromised_drug_targets || []).join(', ') || 'None'}
                        </div>
                    </div>
                `).join('') : `
                    <div style="font-size:0.82rem; color:var(--text-muted); padding:8px 0;">
                        No canonical pathways significantly disrupted for this locus in current patient profile.
                    </div>
                `}
            </div>

            <!-- Targeted Therapies & Bypass Status -->
            <div style="background:rgba(255,255,255,0.03); border:1px solid rgba(255,255,255,0.06); border-radius:6px; padding:12px;">
                <div style="font-size:0.75rem; text-transform:uppercase; color:var(--primary); font-weight:700; margin-bottom:8px;">
                    Targeted Therapies (Knowledge Base)
                </div>
                ${topDrug ? `
                    <div style="background:rgba(16,185,129,0.12); border:1px solid rgba(16,185,129,0.3); border-radius:4px; padding:6px 10px; margin-bottom:8px;">
                        <span style="font-size:0.75rem; color:#a7f3d0;">Active Recommendation:</span>
                        <div style="font-size:0.85rem; font-weight:700; color:#ffffff;">${topDrug.drug_name || topDrug.name} (${Math.round((topDrug.sensitivity_score || 0) * 100)}% Sensitivity)</div>
                    </div>
                ` : ''}
                ${knownDrugs.length > 0 ? knownDrugs.map(d => `
                    <div style="font-size:0.8rem; margin-bottom:4px; display:flex; justify-content:space-between; gap:6px;">
                        <strong style="color:#ffffff;">${d.name}</strong>
                        <span style="color:var(--text-secondary); font-size:0.75rem;">${d.status}</span>
                    </div>
                `).join('') : `
                    <div style="font-size:0.8rem; color:var(--text-muted);">
                        No direct single-agent small molecule kinase inhibitors targeting this effector.
                    </div>
                `}
            </div>
        </div>
    `;
}

function getNodeCategoryTitle(id) {
    const categories = {
        'EGFR': 'Receptor Tyrosine Kinase (RTK)',
        'MET': 'Hepatocyte Growth Factor Receptor (Bypass RTK)',
        'ALK': 'Anaplastic Lymphoma Kinase (Fusion RTK)',
        'KRAS': 'Membrane-Associated Small GTPase',
        'PIK3CA': 'Phosphatidylinositol 4,5-bisphosphate 3-kinase (p110α)',
        'PTEN': 'Phosphatase and Tensin Homolog (Tumor Suppressor)',
        'BRAF': 'RAF Kinase Family (Serine/Threonine Kinase)',
        'AKT': 'Protein Kinase B (Cell Survival Effector)',
        'TP53': 'Cellular Tumor Antigen p53 (Genome Guardian)',
        'PROLIFERATION': 'Cell Division & Mitogenic Transcription Endpoint',
        'SURVIVAL': 'Anti-Apoptotic Viability Endpoint',
        'RESISTANCE': 'Therapeutic Bypass Escape Phenotype'
    };
    return categories[id] || 'Intracellular Signaling Element';
}

function getNodePathwaysString(id) {
    const pw = {
        'EGFR': 'RTK Signaling, ERK MAPK Signaling',
        'MET': 'RTK Signaling, MET Bypass Cross-talk',
        'ALK': 'RTK Signaling, ALK Fusion Translocation',
        'KRAS': 'RAS Pathway, MAPK Cascade, PI3K Activation',
        'PIK3CA': 'PI3K/AKT/mTOR Signaling',
        'PTEN': 'PI3K/AKT Regulatory Inactivation',
        'BRAF': 'MAPK/ERK Proliferation Signaling',
        'AKT': 'PI3K/AKT/mTOR Anti-Apoptosis',
        'TP53': 'p53 Apoptosis & Cell Cycle Checkpoint',
        'PROLIFERATION': 'Nuclear Gene Expression',
        'SURVIVAL': 'Mitochondrial Apoptotic Regulation',
        'RESISTANCE': 'Oncogenic Kinase Re-Wiring'
    };
    return pw[id] || 'Canonical Oncogenic Signaling';
}

// Explicit global attachments for cross-script resilience
if (typeof window !== 'undefined') {
    window.renderWaterfallPlot = renderWaterfallPlot;
    window.renderDivergingSHAP = renderDivergingSHAP;
    window.renderSignalingPathwayDiagram = renderSignalingPathwayDiagram;
    window.setWaterfallView = setWaterfallView;
    window.renderFallbackWaterfallSVG = renderFallbackWaterfallSVG;
    window.renderFallbackSHAP = renderFallbackSHAP;
    window.setSignalingViewMode = setSignalingViewMode;
    window.inspectSignalingNode = inspectSignalingNode;
    window.closeSignalingNodeInspector = closeSignalingNodeInspector;
}
