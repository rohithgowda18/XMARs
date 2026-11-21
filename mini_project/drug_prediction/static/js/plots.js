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

/**
 * 3. Interactive Oncogenic Signaling Pathway & Bypass Resistance Network
 * Topologically maps Extracellular Receptors -> Secondary Messengers -> Nuclear Effectors
 * Highlights mutated drivers, drug target blockades, and constitutive bypass escape routes.
 */
function renderSignalingPathwayDiagram(data, containerId = 'pathwayDiagramContainer') {
    const container = document.getElementById(containerId);
    if (!container) return;

    // Extract mutated genes and evaluated drugs
    const mutatedGenes = new Set();
    const mutations = data.mutations_analyzed || (data.mutation_summary?.mutations ? data.mutation_summary.mutations.map(m => m.gene) : Object.keys(window.selectedGenes || {}));
    mutations.forEach(g => mutatedGenes.add(String(g).toUpperCase()));

    // Extract top recommended drug and its target
    const drugs = data.drug_predictions || data.drug_strategy?.top_10 || [];
    const topDrug = drugs.length > 0 ? drugs[0] : null;
    const topDrugName = topDrug ? (topDrug.drug_name || topDrug.name) : 'Osimertinib';
    const topDrugTarget = topDrug ? String(topDrug.targets || topDrug.target || 'EGFR').toUpperCase() : 'EGFR';

    // Check for bypass resistance (e.g. EGFR inhibited while MET, KRAS or PIK3CA is mutated)
    const hasEGFR = mutatedGenes.has('EGFR');
    const hasMET = mutatedGenes.has('MET');
    const hasKRAS = mutatedGenes.has('KRAS') || mutatedGenes.has('BRAF');
    const hasPI3K = mutatedGenes.has('PIK3CA');
    const isBypassActive = (hasEGFR && (hasMET || hasKRAS || hasPI3K)) || (hasMET && hasKRAS);

    // Topological layout nodes: id, label, role, layer, x, y
    const nodes = [
        // Layer 0: Extracellular Ligand / Membrane Receptors
        { id: 'EGFR', label: 'EGFR / HER2', type: 'receptor', x: 200, y: 80, role: 'RTK Receptor' },
        { id: 'MET', label: 'c-MET', type: 'receptor', x: 450, y: 80, role: 'Bypass Kinase' },
        { id: 'ALK', label: 'ALK / RET', type: 'receptor', x: 700, y: 80, role: 'Translocation RTK' },

        // Layer 1: Intracellular Adaptors & Key Hubs
        { id: 'KRAS', label: 'KRAS', type: 'adaptor', x: 260, y: 190, role: 'MAPK Hub' },
        { id: 'PIK3CA', label: 'PI3K (p110α)', type: 'adaptor', x: 500, y: 190, role: 'Survival Hub' },
        { id: 'PTEN', label: 'PTEN', type: 'tumor_suppressor', x: 670, y: 190, role: 'Brake (Suppressor)' },

        // Layer 2: Intermediate Kinase Cascade
        { id: 'BRAF', label: 'BRAF / MEK', type: 'cascade', x: 260, y: 290, role: 'Proliferation Cascade' },
        { id: 'AKT', label: 'AKT / mTOR', type: 'cascade', x: 500, y: 290, role: 'Anti-Apoptotic' },
        { id: 'TP53', label: 'p53', type: 'tumor_suppressor', x: 740, y: 290, role: 'Genome Guardian' },

        // Layer 3: Nuclear Transcriptional & Proliferative Response
        { id: 'PROLIFERATION', label: 'Cell Proliferation & Survival', type: 'phenotype', x: 380, y: 400, role: 'Malignant Growth' },
        { id: 'RESISTANCE', label: 'Targeted TKI Resistance', type: 'phenotype', x: 620, y: 400, role: 'Therapeutic Failure' }
    ];

    // Canonical signaling edges: from, to, type ('activate', 'inhibit', 'bypass')
    const edges = [
        { from: 'EGFR', to: 'KRAS', type: 'activate' },
        { from: 'EGFR', to: 'PIK3CA', type: 'activate' },
        { from: 'MET', to: 'PIK3CA', type: 'bypass' },
        { from: 'MET', to: 'KRAS', type: 'bypass' },
        { from: 'ALK', to: 'KRAS', type: 'activate' },
        { from: 'ALK', to: 'PIK3CA', type: 'activate' },
        { from: 'KRAS', to: 'BRAF', type: 'activate' },
        { from: 'PIK3CA', to: 'AKT', type: 'activate' },
        { from: 'PTEN', to: 'AKT', type: 'inhibit' },
        { from: 'BRAF', to: 'PROLIFERATION', type: 'activate' },
        { from: 'AKT', to: 'PROLIFERATION', type: 'activate' },
        { from: 'AKT', to: 'RESISTANCE', type: 'bypass' },
        { from: 'TP53', to: 'PROLIFERATION', type: 'inhibit' }
    ];

    // SVG coordinate helper
    const nodeMap = {};
    nodes.forEach(n => { nodeMap[n.id] = n; });

    let svgEdges = '';
    edges.forEach(e => {
        const source = nodeMap[e.from];
        const target = nodeMap[e.to];
        if (!source || !target) return;

        const isBypass = e.type === 'bypass' && isBypassActive;
        const color = isBypass ? '#eab308' : e.type === 'inhibit' ? '#64748b' : '#38bdf8';
        const strokeW = isBypass ? 3 : 2;
        const dash = isBypass ? '6,4' : e.type === 'inhibit' ? '4,4' : 'none';

        // Draw curved quadratic Bezier line
        const midX = (source.x + target.x) / 2 + (e.from === 'MET' && e.to === 'KRAS' ? -30 : 0);
        const midY = (source.y + target.y) / 2;

        svgEdges += `
            <path d="M ${source.x} ${source.y} Q ${midX} ${midY} ${target.x} ${target.y}" 
                  fill="none" stroke="${color}" stroke-width="${strokeW}" stroke-dasharray="${dash}" opacity="${isBypass ? 0.95 : 0.6}">
                ${isBypass ? '<animate attributeName="stroke-dashoffset" values="40;0" dur="1.2s" repeatCount="indefinite" />' : ''}
            </path>
        `;
    });

    let svgNodes = '';
    nodes.forEach(n => {
        const isMutated = mutatedGenes.has(n.id);
        const isInhibited = n.id === topDrugTarget;
        
        let fillColor = 'rgba(30, 41, 59, 0.9)';
        let strokeColor = '#475569';
        let glow = '';

        if (isMutated) {
            fillColor = 'rgba(239, 68, 68, 0.25)';
            strokeColor = '#ef4444';
            glow = 'filter="drop-shadow(0 0 8px rgba(239, 68, 68, 0.7))"';
        } else if (isInhibited) {
            fillColor = 'rgba(16, 185, 129, 0.2)';
            strokeColor = '#10b981';
            glow = 'filter="drop-shadow(0 0 8px rgba(16, 185, 129, 0.6))"';
        } else if (n.type === 'phenotype') {
            fillColor = n.id === 'RESISTANCE' && isBypassActive ? 'rgba(234, 179, 8, 0.2)' : 'rgba(15, 23, 42, 0.9)';
            strokeColor = n.id === 'RESISTANCE' && isBypassActive ? '#eab308' : '#334155';
        }

        const width = n.type === 'phenotype' ? 200 : 130;
        const height = 48;
        const rx = n.type === 'phenotype' ? 8 : 24;

        svgNodes += `
            <g transform="translate(${n.x - width / 2}, ${n.y - height / 2})" ${glow} style="cursor:pointer;">
                <rect width="${width}" height="${height}" rx="${rx}" fill="${fillColor}" stroke="${strokeColor}" stroke-width="2" />
                <text x="${width / 2}" y="22" fill="#ffffff" font-size="12" font-weight="700" text-anchor="middle" font-family="Inter, sans-serif">
                    ${n.label}
                </text>
                <text x="${width / 2}" y="36" fill="${isMutated ? '#fca5a5' : isInhibited ? '#6ee7b7' : '#94a3b8'}" font-size="9" text-anchor="middle" font-family="Inter, sans-serif">
                    ${isMutated ? '● MUTATED DRIVER' : isInhibited ? `⚡ INHIBITED (${topDrugName})` : n.role}
                </text>
                ${isInhibited ? `
                    <circle cx="16" cy="16" r="8" fill="#10b981" />
                    <text x="16" y="20" fill="#000" font-size="10" font-weight="bold" text-anchor="middle">Rx</text>
                ` : ''}
            </g>
        `;
    });

    const statusBanner = isBypassActive
        ? `<div style="position:absolute; top:14px; left:20px; background:rgba(234, 179, 8, 0.15); border:1px solid rgba(234, 179, 8, 0.4); padding:6px 14px; border-radius:6px; color:#fef08a; font-size:0.78rem; display:flex; align-items:center; gap:8px;">
             <span>⚠️</span> <strong>Bypass Circuit Activated:</strong> Dual activation detected (e.g. MET/KRAS) bypassing primary receptor blockade.
           </div>`
        : `<div style="position:absolute; top:14px; left:20px; background:rgba(16, 185, 129, 0.15); border:1px solid rgba(16, 185, 129, 0.35); padding:6px 14px; border-radius:6px; color:#a7f3d0; font-size:0.78rem; display:flex; align-items:center; gap:8px;">
             <span>🛡️</span> <strong>Linear Target Control:</strong> Canonical cascade under direct target inhibition.
           </div>`;

    container.innerHTML = `
        ${statusBanner}
        <div style="position:absolute; top:14px; right:20px; color:#64748b; font-size:0.75rem;">
            Extracellular Membrane ➔ Intracellular Transduction ➔ Gene Transcription
        </div>
        <svg width="100%" height="460" viewBox="0 0 900 460" style="display:block; margin:0 auto;">
            <!-- Membrane reference line -->
            <line x1="60" y1="125" x2="840" y2="125" stroke="rgba(255,255,255,0.08)" stroke-dasharray="4,4" />
            <text x="70" y="120" fill="#475569" font-size="10" font-family="Inter, sans-serif">CELL PLASMA MEMBRANE</text>

            <!-- Nuclear boundary line -->
            <line x1="60" y1="355" x2="840" y2="355" stroke="rgba(255,255,255,0.08)" stroke-dasharray="4,4" />
            <text x="70" y="350" fill="#475569" font-size="10" font-family="Inter, sans-serif">NUCLEAR TRANSLOCATION</text>

            <!-- Rendered Edges & Nodes -->
            ${svgEdges}
            ${svgNodes}
        </svg>
    `;
}

// Explicit global attachments for cross-script resilience
if (typeof window !== 'undefined') {
    window.renderWaterfallPlot = renderWaterfallPlot;
    window.renderDivergingSHAP = renderDivergingSHAP;
    window.renderSignalingPathwayDiagram = renderSignalingPathwayDiagram;
    window.setWaterfallView = setWaterfallView;
    window.renderFallbackWaterfallSVG = renderFallbackWaterfallSVG;
    window.renderFallbackSHAP = renderFallbackSHAP;
}
