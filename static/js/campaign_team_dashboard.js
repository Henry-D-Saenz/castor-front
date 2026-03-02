/**
 * Campaign Team Dashboard V2 - JavaScript
 * Dashboard integrado para el equipo de campaña electoral.
 * Control electoral, zonas de riesgo y coordinación de testigos.
 */

// ============================================================
// TYPE DEFINITIONS (mirrors backend/app/schemas/)
// ============================================================

/**
 * Mesa de votación con clasificación de riesgo OCR.
 * Generada en processAlertsData() desde alertas del War Room.
 * @typedef {Object} Mesa
 * @property {number} id
 * @property {string} mesaId - ID compuesto: DEPT-MUNI-ZONA-PUESTO-MESA
 * @property {string} dept - Nombre del departamento
 * @property {string} muni - Nombre del municipio
 * @property {string} puesto - Nombre del puesto de votación
 * @property {string} location - Ubicación completa
 * @property {number|null} ocrConfidence - Confianza OCR 0-100 (null si no disponible)
 * @property {string} reason - Motivo de la alerta
 * @property {number} totalVotes - Total de votos en la mesa
 * @property {'OPEN'|'ACKNOWLEDGED'|'INVESTIGATING'|'RESOLVED'|'FALSE_POSITIVE'} status
 * @property {'INFO'|'LOW'|'MEDIUM'|'HIGH'|'CRITICAL'} severity
 * @property {'high'|'medium'|'low'|'unknown'} riskLevel - Clasificación: thresholds from /api/e14-data/config
 */

/**
 * Votos agregados por partido político (desde E-14 OCR).
 * Generada en processE14VotesData() o processVotesData().
 * @typedef {Object} PartyVote
 * @property {number} id
 * @property {string} party_name - Nombre normalizado del partido
 * @property {string} party_code - Código del partido
 * @property {number} total_votes - Total de votos del partido
 * @property {number} percentage - Porcentaje del total (0-100)
 * @property {number} ocrConfidence - Confianza OCR promedio (0-100)
 * @property {number} mesas_count - Cantidad de mesas donde aparece
 * @property {number} reviewable_votes - Votos en mesas con anomalías
 * @property {number} reviewable_mesas - Mesas con anomalías
 * @property {number} votes_high_risk - Votos con confianza <70%
 * @property {number} votes_medium_risk - Votos con confianza 70-85%
 * @property {number} votes_low_risk - Votos con confianza ≥85%
 * @property {'high'|'medium'|'low'} riskLevel
 */

/**
 * Testigo electoral registrado.
 * @typedef {Object} Witness
 * @property {number} id
 * @property {string} name - Nombre completo
 * @property {string} phone - Teléfono (10-15 dígitos)
 * @property {'available'|'busy'} status
 * @property {boolean} push_enabled - Push notifications activas
 * @property {string} [coverage_dept_name] - Departamento que cubre
 * @property {string} [coverage_muni_name] - Municipio que cubre
 * @property {string} [coverage_station_name] - Puesto que cubre
 * @property {string} [coverageDisplay] - Texto formateado de cobertura
 * @property {string} [currentLocation] - Ubicación actual
 */

/**
 * Registro de llamado a testigo.
 * @typedef {Object} CallLogEntry
 * @property {number} id
 * @property {Date} timestamp
 * @property {string} mesa - ID de la mesa
 * @property {string} witness - Nombre del testigo
 * @property {'enviado'|'completado'} status
 * @property {string} message - Mensaje enviado
 */

/**
 * Candidato en seguimiento (tracking cards).
 * @typedef {Object} TrackedCandidate
 * @property {number} id
 * @property {string} name
 * @property {string} party
 * @property {string} color - Color hex del partido
 * @property {number} votes - Votos E-14
 * @property {number} percentage - Porcentaje (0-100)
 * @property {number} mesas - Mesas procesadas
 * @property {number|null} position - Posición en ranking
 * @property {'up'|'down'|'stable'} trend
 * @property {number} trendValue - Cambio porcentual
 * @property {number} [coverage] - Cobertura (0-100)
 */

/**
 * Estadísticas del E14 JSON Store (endpoint /api/e14-data/stats).
 * @typedef {Object} E14Stats
 * @property {number} total_forms - Total de formularios procesados
 * @property {number} unique_forms - Formularios únicos (sin duplicados)
 * @property {number} total_votos - Total de votos válidos
 * @property {number} votos_blancos - Total votos en blanco
 * @property {number} votos_nulos - Total votos nulos
 * @property {number} avg_confidence - Confianza promedio (0-1)
 * @property {number} arithmetic_errors - Errores aritméticos detectados
 * @property {number} needs_review - Formularios que necesitan revisión
 * @property {number} high_risk - Formularios de alto riesgo
 * @property {Object} [ocr_quality] - Calidad OCR por nivel de riesgo
 * @property {string} [ocr_quality.pct_of_total]
 * @property {string} [ocr_quality.avg_confidence]
 * @property {string} [ocr_quality.min_confidence]
 * @property {number} [ocr_quality.arithmetic_errors]
 * @property {number} [ocr_quality.warnings_count]
 */

/**
 * Formulario anómalo del E-14 (endpoint /api/e14-data/anomalies).
 * @typedef {Object} AnomalousForm
 * @property {number} id
 * @property {string} mesa_id - ID compuesto de la mesa
 * @property {string} departamento
 * @property {string} municipio
 * @property {number} ocr_confidence - Confianza OCR (0-1)
 * @property {'high_risk'|'needs_review'|'arithmetic_error'} issue
 * @property {number} [votos_nulos]
 * @property {number} [votos_blancos]
 * @property {number} [party_sum]
 * @property {string} [detail]
 */

/**
 * Datos de anomalías agrupados (response de /api/e14-data/anomalies).
 * @typedef {Object} AnomaliesData
 * @property {number} total - Total de anomalías
 * @property {number} high_risk_count
 * @property {number} needs_review_count
 * @property {number} arithmetic_errors_count
 * @property {AnomalousForm[]} high_risk
 * @property {AnomalousForm[]} needs_review
 * @property {AnomalousForm[]} arithmetic_errors
 */

/**
 * Datos globales del E14 Store almacenados en window.e14Data.
 * @typedef {Object} E14DashboardData
 * @property {E14Stats} stats
 * @property {AnomaliesData} anomalies
 * @property {PartyVote[]} partyTotals
 * @property {Object[]} departamentos
 * @property {MunicipalityVotes[]} votesByMunicipality
 */

/**
 * Votos por municipio (endpoint /api/e14-data/votes-by-municipality).
 * @typedef {Object} MunicipalityVotes
 * @property {string} departamento
 * @property {string} municipio
 * @property {number} total_mesas
 * @property {number} total_votos
 * @property {number} votos_blancos
 * @property {number} votos_nulos
 */

/**
 * Estado de los filtros del dashboard.
 * @typedef {Object} FilterState
 * @property {string} dept - Departamento seleccionado
 * @property {string} muni - Municipio seleccionado
 * @property {string} puesto - Puesto seleccionado
 * @property {string} mesa - Mesa seleccionada
 * @property {string} risk - Nivel de riesgo: 'high'|'medium'|'low'|''
 */

// ============================================================
// SEEN MESAS — localStorage persistence for "NUEVA" badge
// ============================================================

function getSeenMesas() {
    try {
        return new Set(JSON.parse(localStorage.getItem('castor_e14_seen') || '[]'));
    } catch { return new Set(); }
}

function markMesaAsSeen(mesaId) {
    const seen = getSeenMesas();
    seen.add(String(mesaId));
    localStorage.setItem('castor_e14_seen', JSON.stringify([...seen]));
}

// ============================================================
// GLOBAL STATE
// ============================================================

/** @type {number} */
let currentContestId = 1;
/** @type {number|null} */
let refreshInterval = null;
const REFRESH_INTERVAL_MS = 30000; // 30 seconds

// Data stores
/** @type {Mesa[]} */
let allMesas = [];
/** @type {PartyVote[]} */
let allVotes = [];
/** @type {Witness[]} - kept for incident assignment compatibility */
let allWitnesses = [];
/** @type {Object<string, Object>|null} */
let TESSERACT_LOOKUP = null;
let tesseractLookupLoaded = false;

/** @type {FilterState} */
let filters = {
    dept: '',
    muni: '',
    puesto: '',
    mesa: '',
    risk: ''
};

// Current selection for witness calling
/** @type {Mesa|null} */
/** @type {Witness|null} */

// Chart instances
let partyChart = null;
let riskChart = null;

// ── OCR confidence thresholds (synced from backend /api/e14-data/config) ──
// Defaults match e14_constants.py; overridden by loadE14Config() on init.
let OCR_HIGH_RISK = 70;    // confidence < 70 → high risk
let OCR_MEDIUM_RISK = 85;  // 70 ≤ conf < 85 → medium risk; ≥ 85 → low risk
let OCR_LEGIBILITY = 75;   // confidence < 75 → needs_review / illegible
let ARITH_WARN_TOL = 2;    // abs(fullSum - total_votos) tolerance (synced from backend)

/** Classify confidence (0-100) into 'high', 'medium', or 'low' risk. */
function classifyOcrRisk(confidence) {
    if (confidence < OCR_HIGH_RISK) return 'high';
    if (confidence < OCR_MEDIUM_RISK) return 'medium';
    return 'low';
}

/** Return CSS class for confidence badge. */
function confidenceClass(confidence) {
    if (confidence < OCR_HIGH_RISK) return 'low';
    if (confidence < OCR_MEDIUM_RISK) return 'medium';
    return 'high';
}

// Chart.js default config
const chartDefaults = {
    responsive: true,
    maintainAspectRatio: false,
    plugins: {
        legend: {
            labels: {
                color: '#111111',
                font: { family: "'Source Sans 3', sans-serif" }
            }
        }
    },
    scales: {
        x: {
            ticks: { color: '#444444' },
            grid: { color: 'rgba(0, 0, 0, 0.08)' }
        },
        y: {
            ticks: { color: '#444444' },
            grid: { color: 'rgba(0, 0, 0, 0.08)' }
        }
    }
};

// ============================================================
// INITIALIZATION
// ============================================================

document.addEventListener('DOMContentLoaded', () => {
    setupTabs();
    setupFilters();
    setupTableSorting();
    setupModalCloseOnOverlay();

    // Initial load
    loadDashboardData();

    // Webhook-first mode: no periodic polling refresh.

    // Init mapa — esperar a Leaflet si aún no está listo (defer puede cargar tarde)
    if (document.getElementById('colombia-map')) {
        if (typeof L !== 'undefined') {
            initColombiaMap();
        } else {
            window.addEventListener('load', initColombiaMap);
        }
    }
});

// Setup click-outside-to-close for all modals
function setupModalCloseOnOverlay() {
    document.querySelectorAll('.modal-overlay').forEach(overlay => {
        overlay.addEventListener('click', (e) => {
            // Close only if clicking directly on overlay (not on modal content)
            if (e.target === overlay) {
                overlay.classList.remove('active');
            }
        });
    });
}

// ============================================================
// TAB NAVIGATION
// ============================================================

function setupTabs() {
    const tabButtons = document.querySelectorAll('.tab-btn');
    const tabContents = document.querySelectorAll('.tab-content');

    tabButtons.forEach(btn => {
        btn.addEventListener('click', () => {
            const tabId = btn.dataset.tab;

            // Update buttons
            tabButtons.forEach(b => {
                b.classList.remove('active');
                b.setAttribute('aria-selected', 'false');
            });
            btn.classList.add('active');
            btn.setAttribute('aria-selected', 'true');

            // Update content
            tabContents.forEach(content => {
                content.classList.remove('active');
            });
            document.getElementById(tabId).classList.add('active');

            // Load tab-specific data
            loadTabData(tabId);
        });
    });
}

function loadTabData(tabId) {
    switch (tabId) {
        case 'contienda':
            renderContiendaTab();
            break;
    }
}

// ============================================================
// DATA LOADING
// ============================================================

async function loadDashboardData() {
    showLoading(true);

    // Helper to safely parse JSON response
    const safeJson = async (response, fallback = { success: false }) => {
        try {
            if (!response.ok) {
                console.warn(`API returned ${response.status}: ${response.statusText}`);
                return fallback;
            }
            return await response.json();
        } catch (e) {
            console.warn('Failed to parse JSON response:', e);
            return fallback;
        }
    };

    try {
        await loadMunicipioCatalog();
        // loadTesseractLookup() retired — Tesseract lookup removed, API data takes priority

        // Load E14 config thresholds from backend (best-effort)
        try {
            const cfgResp = await fetch('/api/e14-data/config');
            if (cfgResp.ok) {
                const cfg = await cfgResp.json();
                OCR_HIGH_RISK = (cfg.ocr_high_risk || 0.70) * 100;
                OCR_MEDIUM_RISK = (cfg.ocr_medium_risk || 0.85) * 100;
                OCR_LEGIBILITY = (cfg.anomaly_needs_review || 0.75) * 100;
                ARITH_WARN_TOL = cfg.arith_warn_tol ?? 2;
                console.log(`E14 config loaded: high_risk<${OCR_HIGH_RISK}%, medium<${OCR_MEDIUM_RISK}%, arith_tol=${ARITH_WARN_TOL}`);
            }
        } catch (_) { /* use defaults */ }

        // Parallel fetch: E14 JSON store endpoints + legacy
        const [
            statsResponse, votesResponse, alertsResponse, e14Response,
            e14StatsResp, e14AnomaliesResp, e14PartyResp, e14DeptResp, e14VotesMuniResp,
            e14PmsnResp
        ] = await Promise.all([
            fetch(`/api/campaign-team/war-room/stats?contest_id=${currentContestId}`).catch(() => null),
            fetch(`/api/campaign-team/reports/votes-by-candidate?contest_id=${currentContestId}`).catch(() => null),
            fetch(`/api/campaign-team/war-room/alerts?contest_id=${currentContestId}&limit=100`).catch(() => null),
            fetch(`/api/campaign-team/e14-live?limit=500`).catch(() => null),
            fetch('/api/e14-data/stats').catch(() => null),
            fetch('/api/e14-data/anomalies').catch(() => null),
            fetch('/api/e14-data/party-totals?limit=30').catch(() => null),
            fetch('/api/e14-data/departamentos').catch(() => null),
            fetch('/api/e14-data/votes-by-municipality').catch(() => null),
            fetch('/api/e14-data/pmsn-alerts').catch(() => null),
        ]);

        const statsData = statsResponse ? await safeJson(statsResponse) : { success: false };
        const votesData = votesResponse ? await safeJson(votesResponse) : { success: false };
        const alertsData = alertsResponse ? await safeJson(alertsResponse) : { success: false };
        const e14Data = e14Response ? await safeJson(e14Response) : { success: false };

        // E14 JSON store data — stored globally for all tabs
        const e14Stats = e14StatsResp ? await safeJson(e14StatsResp, {}) : {};
        const e14Anomalies = e14AnomaliesResp ? await safeJson(e14AnomaliesResp, {}) : {};
        const e14Party = e14PartyResp ? await safeJson(e14PartyResp, []) : [];
        const e14Dept = e14DeptResp ? await safeJson(e14DeptResp, []) : [];
        const e14VotesMuni = e14VotesMuniResp ? await safeJson(e14VotesMuniResp, []) : [];
        const e14Pmsn = e14PmsnResp ? await safeJson(e14PmsnResp, {}) : {};

        window.e14Data = {
            stats: e14Stats,
            anomalies: e14Anomalies,
            partyTotals: Array.isArray(e14Party) ? e14Party : [],
            departamentos: Array.isArray(e14Dept) ? e14Dept : [],
            votesByMunicipality: Array.isArray(e14VotesMuni) ? e14VotesMuni : [],
            pmsnAlerts: e14Pmsn,
        };

        // Process and store data
        if (statsData.success) {
            processStatsData(statsData);
        }

        if (votesData.success) {
            processVotesData(votesData);
        }

        if (alertsData.success) {
            processAlertsData(alertsData);
        }

        // Render E-14 live form
        if (e14Data.success) {
            const prevCount = (window.e14LiveData?.forms || []).length;
            window.e14LiveData = e14Data;
            buildE14GeoLookup(e14Data);

            if (typeof processE14VotesData === 'function') {
                processE14VotesData();
            }

            // Recargar mapa solo si llegaron actas nuevas
            const newCount = (e14Data.forms || []).length;
            if (colombiaMap && newCount !== prevCount) {
                loadChoroplethData(currentMapMode);
            }
        }

        // Populate filters
        populateFilters();

        // Render initial tab (contienda)
        renderContiendaTab();

        updateTimestamp();

    } catch (error) {
        console.error('Error loading dashboard data:', error);
        populateFilters();
        renderContiendaTab();
    } finally {
        showLoading(false);
    }
}

function processStatsData(data) {
    // Store raw stats
    window.dashboardStats = data;
}

function processVotesData(data) {
    console.log('processVotesData received:', data);

    // Store candidates data from API
    const candidates = data.candidates || data.by_candidate || [];
    console.log('Found candidates:', candidates.length);

    // Update tracked candidates with API data
    candidates.forEach(apiCandidate => {
        const candidate = trackedCandidates.find(c => c.name === apiCandidate.name);
        if (candidate) {
            candidate.votes = apiCandidate.votes || 0;
            candidate.percentage = apiCandidate.percentage || 0;
            candidate.mesas = apiCandidate.mesas_processed || 0;
            candidate.trend = apiCandidate.trend || 'stable';
            candidate.trendValue = apiCandidate.trend_value || 0;
            candidate.color = apiCandidate.color || candidate.color;
            candidate.coverage = apiCandidate.coverage_pct || 0;
            console.log(`Updated ${candidate.name}: ${candidate.votes} votes`);
        } else {
            console.warn(`Candidate not found: ${apiCandidate.name}`);
        }
    });

    // Store votes with risk classification
    allVotes = candidates.map((vote, index) => ({
        ...vote,
        id: index + 1,
        party: vote.party || 'Sin partido',
        ocrConfidence: (vote.confidence || 0.85) * 100,
        dept: data.dept || 'Nacional',
        muni: data.muni || 'Nacional',
        puesto: `Puesto ${Math.floor(index / 5) + 1}`,
        mesaNum: (index % 10) + 1
    }));

    // Add risk classification (thresholds from e14_constants via /api/e14-data/config)
    allVotes.forEach(vote => { vote.riskLevel = classifyOcrRisk(vote.ocrConfidence); });
}

function processE14VotesData() {
    // Priority 1: E14 JSON store party totals (pre-aggregated from tesseract)
    // Priority 2: e14LiveData party_summary
    const jsonStoreParties = window.e14Data?.partyTotals || [];
    let partySummary = window.e14LiveData?.party_summary || [];
    let totalVotesFromAPI = window.e14LiveData?.total_votes || 0;

    // Use JSON store data if available (more reliable)
    if (jsonStoreParties.length > 0) {
        partySummary = jsonStoreParties.map(p => ({
            party_name: p.party_name,
            party_code: '',
            total_votes: p.total_votes,
            avg_confidence: p.avg_confidence,
            mesas_count: p.mesas_count,
            reviewable_votes: p.reviewable_votes || 0,
            reviewable_mesas: p.reviewable_mesas || 0,
            votes_high_risk: p.votes_high_risk || 0,
            votes_medium_risk: p.votes_medium_risk || 0,
            votes_low_risk: p.votes_low_risk || 0,
        }));
    }

    // Bug 3: always derive the denominator from the actual sum of party votes,
    // never from total_votos (form headers). When OCR inflates party votes the
    // two numbers diverge and percentages exceed 100%.
    const totalFromParties = partySummary.reduce((s, p) => s + (p.total_votes || 0), 0);
    if (totalFromParties > 0) totalVotesFromAPI = totalFromParties;

    // If party_summary is available (Tesseract data), use it directly
    if (partySummary.length > 0) {
        console.log(`Using party_summary with ${partySummary.length} parties, ${totalVotesFromAPI} total votes`);

        allVotes = partySummary.map((partido, index) => ({
            id: index + 1,
            party_name: partido.party_name,
            party_code: partido.party_code || '',
            total_votes: partido.total_votes,
            percentage: totalVotesFromAPI > 0 ? (partido.total_votes / totalVotesFromAPI) * 100 : 0,
            ocrConfidence: (partido.avg_confidence || 0.85) * 100,
            mesas_count: partido.mesas_count || 0,
            reviewable_votes: partido.reviewable_votes || 0,
            reviewable_mesas: partido.reviewable_mesas || 0,
            votes_high_risk: partido.votes_high_risk || 0,
            votes_medium_risk: partido.votes_medium_risk || 0,
            votes_low_risk: partido.votes_low_risk || 0,
            riskLevel: 'low'
        }));

        // Add risk classification (thresholds from e14_constants via /api/e14-data/config)
        allVotes.forEach(vote => { vote.riskLevel = classifyOcrRisk(vote.ocrConfidence); });

        // Already sorted by API, but ensure sort
        allVotes.sort((a, b) => b.total_votes - a.total_votes);

        console.log(`Processed ${allVotes.length} partidos from party_summary (Congress 2022)`);

        // Render party chart + risk donut
        renderPartyList(allVotes);
        renderPartyChart(allVotes);
        renderRiskDonutChart(allVotes);
        return;
    }

    // Fallback: aggregate from forms if no party_summary
    const forms = window.e14LiveData?.forms || [];

    // If no forms, keep empty
    if (forms.length === 0) {
        console.log('No E-14 forms available for party chart');
        allVotes = [];
        renderPartyList(allVotes);
        return;
    }

    // Aggregate votes by partido across all E-14 forms
    const partidoVotes = {};
    let totalVotesAll = 0;

    forms.forEach(form => {
        const partidos = form.partidos || [];
        partidos.forEach(partido => {
            const key = partido.party_code || partido.party_name;
            if (!partidoVotes[key]) {
                partidoVotes[key] = {
                    party_code: partido.party_code,
                    party_name: partido.party_name,
                    total_votes: 0,
                    confidence_sum: 0,
                    count: 0
                };
            }
            // Support both formats: 'votes' (Tesseract) and 'total_votos' (Vision)
            const votes = partido.votes || partido.total_votos || 0;
            partidoVotes[key].total_votes += votes;
            partidoVotes[key].confidence_sum += (partido.confidence || 0) * 100;
            partidoVotes[key].count += 1;
            totalVotesAll += votes;
        });
    });

    // Convert to array and calculate percentages
    allVotes = Object.values(partidoVotes).map((partido, index) => ({
        id: index + 1,
        party_name: partido.party_name || `Partido ${partido.party_code}`,
        party_code: partido.party_code,
        total_votes: partido.total_votes,
        percentage: totalVotesAll > 0 ? (partido.total_votes / totalVotesAll) * 100 : 0,
        ocrConfidence: partido.count > 0 ? partido.confidence_sum / partido.count : 0,
        riskLevel: 'low'
    }));

    // Add risk classification (thresholds from e14_constants via /api/e14-data/config)
    allVotes.forEach(vote => { vote.riskLevel = classifyOcrRisk(vote.ocrConfidence); });

    // Sort by votes descending
    allVotes.sort((a, b) => b.total_votes - a.total_votes);

    console.log(`Processed ${allVotes.length} partidos from E-14 forms`);

    // Render party chart
    renderPartyChart(allVotes);
}

/**
 * Fallback function to populate party chart with tracked candidates data
 * Used when no E-14 forms are available from the API
 */
function useFallbackPartyData() {
    console.log('Fallback party data disabled (no mock data).');
    allVotes = [];
    renderPartyList(allVotes);
}


/**
 * Convierte alertas del War Room en datos de mesa con riesgo OCR.
 * @param {{ success: boolean, alerts: Object[] }} data
 */
function processAlertsData(data) {
    // Convert alerts to mesa risk data
    const alerts = data.alerts || [];

    allMesas = alerts.map((alert, index) => ({
        id: alert.id || index + 1,
        mesaId: alert.mesa_id || 'N/A',
        dept: alert.dept_name || alert.dept_code || '',
        muni: alert.muni_name || alert.muni_code || '',
        puesto: alert.puesto || alert.puesto_name || '',
        location: alert.location || '',
        ocrConfidence: alert.ocr_confidence ? (alert.ocr_confidence * 100) : null,
        reason: alert.message || alert.description || '',
        totalVotes: alert.total_votes || 0,
        status: alert.status || 'OPEN',
        severity: alert.severity || 'MEDIUM'
    }));

    // Add risk classification (thresholds from e14_constants via /api/e14-data/config)
    allMesas.forEach(mesa => {
        if (mesa.ocrConfidence === null || mesa.ocrConfidence === undefined) {
            mesa.riskLevel = 'unknown';
        } else {
            mesa.riskLevel = classifyOcrRisk(mesa.ocrConfidence);
        }
    });
}

function generateMockRiskData() {
    // Mock data generation disabled — OCR problems section removed
}

// ============================================================
// FILTERS
// ============================================================

function setupFilters() {
    ['filter-dept', 'filter-muni', 'filter-puesto', 'filter-mesa', 'filter-risk'].forEach(id => {
        const el = document.getElementById(id);
        if (el) {
            el.addEventListener('change', () => {
                updateFilterState();
            });
        }
    });
}

async function populateFilters() {
    // Primary source: E-14 JSON store endpoints (no dependency on alerts)
    await populateFiltersFromE14();
}

async function populateFiltersFromE14() {
    const deptSelect = document.getElementById('filter-dept');
    const muniSelect = document.getElementById('filter-muni');
    const puestoSelect = document.getElementById('filter-puesto');
    const mesaSelect = document.getElementById('filter-mesa');

    if (!deptSelect || !muniSelect || !puestoSelect || !mesaSelect) return;

    const fetchJson = async (url) => {
        try {
            const r = await fetch(url);
            return r.ok ? await r.json() : [];
        } catch { return []; }
    };

    try {
        const deptsRaw = window.e14Data?.departamentos || [];
        const depts = (Array.isArray(deptsRaw) ? deptsRaw : [])
            .map(d => (typeof d === 'object' && d !== null) ? (d.departamento || d.nombre || d.name || '') : d)
            .filter(Boolean)
            .sort();

        populateSelect('filter-dept', depts, 'Todos');
        populateSelect('filter-muni', [], 'Todos');
        populateSelect('filter-puesto', [], 'Todos');
        populateSelect('filter-mesa', [], 'Todas');

        deptSelect.onchange = async () => {
            const selectedDept = deptSelect.value;
            updateFilterState();

            if (!selectedDept) {
                populateSelect('filter-muni', [], 'Todos');
                populateSelect('filter-puesto', [], 'Todos');
                populateSelect('filter-mesa', [], 'Todas');
                return;
            }

            const muniData = await fetchJson(`/api/e14-data/municipios/${encodeURIComponent(selectedDept)}`);
            const munis = (Array.isArray(muniData) ? muniData : [])
                .map(m => (typeof m === 'object' && m !== null) ? (m.municipio || m.nombre || m.name || '') : m)
                .filter(Boolean)
                .sort();

            populateSelect('filter-muni', munis, 'Todos');
            populateSelect('filter-puesto', [], 'Todos');
            populateSelect('filter-mesa', [], 'Todas');
        };

        muniSelect.onchange = async () => {
            const selectedDept = deptSelect.value;
            const selectedMuni = muniSelect.value;
            updateFilterState();

            if (!selectedDept || !selectedMuni) {
                populateSelect('filter-puesto', [], 'Todos');
                populateSelect('filter-mesa', [], 'Todas');
                return;
            }

            const puestoData = await fetchJson(`/api/e14-data/puestos/${encodeURIComponent(selectedDept)}/${encodeURIComponent(selectedMuni)}`);
            const puestos = (Array.isArray(puestoData) ? puestoData : [])
                .map(p => (typeof p === 'object' && p !== null) ? (p.puesto_cod || p.puesto || p.nombre || p.name || '') : p)
                .filter(Boolean)
                .sort();

            populateSelect('filter-puesto', puestos, 'Todos');
            populateSelect('filter-mesa', [], 'Todas');
        };

        puestoSelect.onchange = async () => {
            const selectedDept = deptSelect.value;
            const selectedMuni = muniSelect.value;
            const selectedPuesto = puestoSelect.value;
            updateFilterState();

            if (!selectedDept || !selectedMuni || !selectedPuesto) {
                populateSelect('filter-mesa', [], 'Todas');
                return;
            }

            const mesaData = await fetchJson(`/api/e14-data/mesas/${encodeURIComponent(selectedDept)}/${encodeURIComponent(selectedMuni)}/${encodeURIComponent(selectedPuesto)}`);
            const mesas = (Array.isArray(mesaData) ? mesaData : [])
                .map(m => (typeof m === 'object' && m !== null) ? (m.mesa_num || m.mesa || m.numero || '') : m)
                .filter(Boolean)
                .map(m => String(m))
                .sort();

            populateSelect('filter-mesa', mesas, 'Todas');
        };
    } catch (e) {
        console.warn('Failed to populate E-14 filters:', e);
        populateSelect('filter-dept', [], 'Todos');
        populateSelect('filter-muni', [], 'Todos');
        populateSelect('filter-puesto', [], 'Todos');
        populateSelect('filter-mesa', [], 'Todas');
    }
}

function populateSelect(id, options, defaultLabel) {
    const select = document.getElementById(id);
    if (!select) return;

    const currentValue = select.value;
    select.innerHTML = `<option value="">${defaultLabel}</option>`;

    options.forEach(opt => {
        const option = document.createElement('option');
        option.value = opt;
        option.textContent = opt;
        select.appendChild(option);
    });

    select.value = currentValue;
}

function updateFilterState() {
    filters.dept = document.getElementById('filter-dept')?.value || '';
    filters.muni = document.getElementById('filter-muni')?.value || '';
    filters.puesto = document.getElementById('filter-puesto')?.value || '';
    filters.mesa = document.getElementById('filter-mesa')?.value || '';
    filters.risk = document.getElementById('filter-risk')?.value || '';
}

async function applyFilters() {
    updateFilterState();
    await refreshFilteredStats();
    renderContiendaTab();
}

async function refreshFilteredStats() {
    const params = new URLSearchParams();
    if (filters.dept) params.set('departamento', filters.dept);
    if (filters.muni) params.set('municipio', filters.muni);
    if (filters.puesto) params.set('puesto', filters.puesto);
    if (filters.mesa) params.set('mesa', filters.mesa);
    if (filters.risk) params.set('risk', filters.risk);
    const qs = params.toString();
    try {
        const resp = await fetch(`/api/e14-data/stats${qs ? '?' + qs : ''}`);
        if (resp.ok) {
            window.e14FilteredStats = await resp.json();
        }
    } catch (e) {
        console.warn('Failed to fetch filtered stats:', e);
    }
}

function clearFilters() {
    ['filter-dept', 'filter-muni', 'filter-puesto', 'filter-mesa', 'filter-risk'].forEach(id => {
        const el = document.getElementById(id);
        if (el) el.value = '';
    });
    filters = { dept: '', muni: '', puesto: '', mesa: '', risk: '' };
    window.e14FilteredStats = null;
    renderContiendaTab();
}

/**
 * @returns {Mesa[]}
 */
function getFilteredMesas() {
    return allMesas.filter(mesa => {
        if (filters.dept && mesa.dept !== filters.dept) return false;
        if (filters.muni && mesa.muni !== filters.muni) return false;
        if (filters.puesto && mesa.puesto !== filters.puesto) return false;
        if (filters.mesa && mesa.mesaId !== filters.mesa) return false;
        if (filters.risk && mesa.riskLevel !== filters.risk) return false;
        return true;
    });
}

/**
 * @returns {PartyVote[]}
 */
function getFilteredVotes() {
    return allVotes.filter(vote => {
        if (filters.dept && vote.dept !== filters.dept) return false;
        if (filters.muni && vote.muni !== filters.muni) return false;
        if (filters.risk && vote.riskLevel !== filters.risk) return false;
        return true;
    });
}

// Make functions global for onclick handlers
window.applyFilters = applyFilters;
window.clearFilters = clearFilters;

// ============================================================
// CONTIENDA ELECTORAL TAB
// ============================================================

function renderContiendaTab() {
    const filteredMesas = getFilteredMesas();
    let filteredVotes = getFilteredVotes();

    // Render tracked candidates
    renderTrackedCandidates();

    // Render party data — isolated so PMSN errors never blank out the party list
    try {
        renderPartyList(filteredVotes);
        renderPartyChart(filteredVotes);
    } catch (e) {
        console.error('Error rendering party section:', e);
    }

    // PMSN Business Rules — isolated so its errors never affect party list rendering
    try {
        renderPMSNSection();
    } catch (e) {
        console.error('Error rendering PMSN section:', e);
    }
}

function extractMesaNum(mesaId) {
    if (!mesaId) return '';
    return mesaId.includes('-') ? mesaId.split('-').pop() : mesaId;
}

// renderOCRProblemsFromE14 removed (section eliminated from dashboard)


// ============================================================
// PMSN BUSINESS RULES SECTION
// ============================================================

const PMSN_THRESHOLD_TARGET = 630000;

const PMSN_RULE_META = {
    'PMSN-01': { label: 'Cámara vs Senado ≥10%', color: '#DC2626' },
    'PMSN-02': { label: 'Tachones/enmendaduras', color: '#DC2626' },
    'PMSN-03': { label: 'Diferencias aritméticas', color: '#DC2626' },
    'PMSN-04': { label: 'E-11 vs E-14', color: '#DC2626' },
    'PMSN-05': { label: '0-1 votos Senado pareto', color: '#F59E0B' },
    'PMSN-06': { label: 'E-14 < 3 firmas', color: '#DC2626' },
    'PMSN-07': { label: 'Voto nulo ≥ 6%', color: '#EAB308' },
};

const PMSN_RISK_COLORS = {
    'R_ALTO': '#E05252',
    'R_MEDIO': '#F07030',
    'R_BAJO': '#D4A017',
};

function renderPMSNRulesList() {
    const container = document.getElementById('pmsn-rules-list');
    if (!container) return;

    const riskLabel = {
        '#DC2626': 'R. Alto',
        '#F59E0B': 'R. Medio',
        '#EAB308': 'R. Bajo',
    };

    const rows = Object.entries(PMSN_RULE_META).map(([id, meta]) => {
        const risk = riskLabel[meta.color] || '';
        return `<div style="display: flex; align-items: center; gap: 0.6rem; padding: 0.45rem 0; border-bottom: 1px solid var(--border-light, #eee);">
            <span style="font-size: 0.72rem; font-weight: 700; color: ${meta.color}; min-width: 68px;">${id}</span>
            <span style="width: 9px; height: 9px; border-radius: 50%; background: ${meta.color}; flex-shrink: 0;"></span>
            <span style="font-size: 0.82rem; color: var(--text, #111); flex: 1; min-width: 0; overflow: visible; white-space: normal;">${meta.label}</span>
            <span style="font-size: 0.7rem; color: ${meta.color}; font-weight: 600; min-width: 55px; text-align: right;">${risk}</span>
        </div>`;
    }).join('');

    container.innerHTML = `
        <div style="background: var(--card-bg, #fff); border-radius: 12px; padding: 1rem 1.2rem; border: 1px solid var(--border, #e5e5e5); margin-bottom: 1rem;">
            <div style="font-weight: 600; font-size: 0.85rem; color: var(--muted, #666); margin-bottom: 0.5rem; text-transform: uppercase; letter-spacing: 0.05em;">7 Reglas de auditoría</div>
            ${rows}
        </div>
    `;
}

function applyIncidentFilters() {
    incidentFilterRiesgo    = document.getElementById('incident-filter-riesgo')?.value  || '';
    incidentFilterDept      = document.getElementById('incident-filter-dept')?.value    || '';
    incidentFilterCorp      = document.getElementById('incident-filter-corp')?.value    || '';
    incidentFilterHoraDesde = document.getElementById('incident-hora-desde')?.value     || '';
    incidentFilterHoraHasta = document.getElementById('incident-hora-hasta')?.value     || '';
    incidentFilterId        = (document.getElementById('incident-filter-id')?.value || '').trim();
    incidentPage = 0;
    renderIncidentTable();
}

function populateIncidentDeptFilter() {
    const sel = document.getElementById('incident-filter-dept');
    if (!sel || !allIncidents.length) return;
    const depts = [...new Set(
        allIncidents.map(i => resolveDeptName(i)).filter(Boolean)
    )].sort();
    const current = sel.value;
    sel.innerHTML = '<option value="">Departamento</option>' +
        depts.map(d => `<option value="${d}"${d === current ? ' selected' : ''}>${escapeHtml(d)}</option>`).join('');
}

function renderPMSNSection() {
    const data = window.e14Data?.pmsnAlerts;
    if (!data) return;

    // Pass data explicitly so renderers don't rely on global timing
    renderPMSNUmbralMesas(data);
    loadIncidentsFromPMSN(data);

    renderPMSNMesasClassification(data);
    if (!data.alerts?.length) return;
    renderPMSNRuleSemaphore(data);
}

function renderPMSNThresholdTracker(data) {
    const container = document.getElementById('pmsn-threshold-tracker');
    if (!container) return;

    // Aggregate PMSN votes from all actas (Senado + Cámara)
    let pmsnVotes = 0;
    for (const p of window.e14Data?.partyTotals || []) {
        if (isPmsnParty(p.party_name || '')) pmsnVotes += (p.total_votes || 0);
    }
    // Fallback to backend-computed total if partyTotals not yet loaded
    if (pmsnVotes === 0) {
        pmsnVotes = data?.total_pmsn_votes ?? window.e14Data?.pmsnAlerts?.total_pmsn_votes ?? 0;
    }

    const pct = Math.min((pmsnVotes / PMSN_THRESHOLD_TARGET) * 100, 100);
    const reached = pmsnVotes >= PMSN_THRESHOLD_TARGET;
    const barColor = reached ? '#16A34A' : '#C9A84C';

    container.innerHTML = `
        <div style="background: var(--card-bg, #fff); border-radius: 12px; padding: 1.2rem; border: 1px solid var(--border, #e5e5e5); margin-bottom: 1rem;">
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.5rem;">
                <span style="font-weight: 600; font-size: 0.95rem; color: var(--text, #111);">Umbral PMSN</span>
                <span style="font-size: 0.85rem; color: var(--muted, #666);">${formatNumber(pmsnVotes)} / ${formatNumber(PMSN_THRESHOLD_TARGET)} votos</span>
            </div>
            <div style="width: 100%; background: #E5E7EB; border-radius: 8px; height: 24px; overflow: hidden;">
                <div style="width: ${pct.toFixed(1)}%; background: ${barColor}; height: 100%; border-radius: 8px; transition: width 0.5s; display: flex; align-items: center; justify-content: center;">
                    <span style="font-size: 0.75rem; font-weight: 600; color: #fff;">${pct.toFixed(1)}%</span>
                </div>
            </div>
            ${reached ? '<div style="margin-top: 0.5rem; padding: 0.4rem 0.8rem; background: #DCFCE7; border-radius: 6px; color: #166534; font-weight: 600; font-size: 0.85rem; text-align: center;">UMBRAL ALCANZADO — Activar defensa de mesas</div>' : ''}
        </div>
    `;
}

function buildPmsnCandidatoTotals(forms) {
    // Returns Map: candidateNum (int) → { votes, actas }
    const totals = new Map();
    for (const f of forms) {
        const counted = new Set(); // deduplicate candidate slots within same acta
        for (const p of (f.partidos || [])) {
            if (!isPmsnParty(p.party_name)) continue;
            const slot = p.candidate_number ?? 0;
            if (counted.has(slot)) continue;
            counted.add(slot);
            if (!totals.has(slot)) totals.set(slot, { votes: 0, actas: 0 });
            const t = totals.get(slot);
            t.votes += (p.votes || 0);
            t.actas += 1;
        }
    }
    return totals;
}

function renderPMSNUmbralMesas(pmsnData) {
    const container = document.getElementById('pmsn-umbral-mesas-section');
    if (!container) return;

    // Use passed data or fall back to global (for direct calls without data)
    const resolvedData = pmsnData || window.e14Data?.pmsnAlerts || {};

    // Aggregate PMSN votes from all actas (Senado + Cámara)
    let pmsnVotes = 0;
    for (const p of window.e14Data?.partyTotals || []) {
        if (isPmsnParty(p.party_name || '')) pmsnVotes += (p.total_votes || 0);
    }
    // Fallback to backend-computed total if partyTotals not yet loaded
    if (pmsnVotes === 0) {
        pmsnVotes = resolvedData.total_pmsn_votes ?? window.e14LiveData?.stats?.pmsn_total_votes ?? 0;
    }

    const BAR_MAX = 1_000_000;
    const thresholdPct = (PMSN_THRESHOLD_TARGET / BAR_MAX) * 100;
    const pct = Math.min((pmsnVotes / BAR_MAX) * 100, 100);
    const reached = pmsnVotes >= PMSN_THRESHOLD_TARGET;
    const barColor = reached ? '#16A34A' : '#C9A84C';

    const { mesas } = classifyPmsnMesas(resolvedData);
    const sorted = [...mesas].sort((a, b) => b.pmsnVotes - a.pmsnVotes).slice(0, 1000);

    // Build candidate totals from ALL processed actas (not just mesas with alerts)
    const allForms = window.e14LiveData?.forms || [];
    const candidateTotals = buildPmsnCandidatoTotals(allForms);

    // Always show Candidato 0, 1 and 100; plus any others found in OCR data
    const ALWAYS_SHOW = [0, 1, 100];
    for (const n of ALWAYS_SHOW) {
        if (!candidateTotals.has(n)) candidateTotals.set(n, { votes: 0, actas: 0 });
    }

    // Sort: 0 first, then numerically ascending
    const candidateRows = [...candidateTotals.entries()]
        .sort(([a], [b]) => a - b)
        .map(([slot, { votes, actas }]) => {
            const label = slot === 0
                ? `Candidato 0 <span style="font-size:0.68rem;color:var(--muted,#888);font-weight:400;">(Lista)</span>`
                : `Candidato ${slot}`;
            const votesDisplay = votes > 0
                ? `<strong>${formatNumber(votes)}</strong>`
                : `<span style="color:var(--muted,#aaa);">—</span>`;
            const actasDisplay = actas > 0
                ? `${actas} acta${actas !== 1 ? 's' : ''} c/votos`
                : `<span style="color:var(--muted,#aaa);">sin datos</span>`;
            return `<tr style="border-bottom:1px solid #eee; font-size:0.82rem;">
                <td style="padding:0.4rem 0.75rem;">${label}</td>
                <td style="text-align:right; padding:0.4rem 0.75rem; font-variant-numeric:tabular-nums;">${votesDisplay}</td>
                <td style="text-align:right; padding:0.4rem 0.75rem; color:var(--muted,#666); font-size:0.78rem;">${actasDisplay}</td>
            </tr>`;
        }).join('');

    // ── Formularios E-14 (X / Y) ──────────────────────────────────────────────
    const totalForms = resolvedData.total_forms || 0;
    const totalPdfs = window.e14Data?.stats?.total_pdfs_available || 0;
    const formsText = (totalPdfs > 0 && totalPdfs > totalForms)
        ? `${totalForms} / ${formatNumber(totalPdfs)} formularios E-14 procesados`
        : `${totalForms} formularios E-14 procesados`;
    const formsHtml = totalForms > 0
        ? `<div style="font-size:0.75rem; color:var(--muted,#666); margin-top:0.2rem;">${formsText}</div>`
        : '';

    // ── Form-level risk counts (deduplicate: highest risk per physical mesa) ─────
    // risk_counts from backend = raw rule firings (1 form can fire 3 rules → 3 entries).
    // We need form-level counts so the badge/legend don't sum >100% of forms.
    const _rPriority = { 'R_ALTO': 3, 'R_MEDIO': 2, 'R_BAJO': 1 };
    const _formRiskMap = {};
    for (const a of (resolvedData.alerts || [])) {
        const mid = a.mesa_id || a.form_id || '';
        const incoming = a.risk_type || 'R_BAJO';
        if (!_formRiskMap[mid] || _rPriority[incoming] > _rPriority[_formRiskMap[mid]]) {
            _formRiskMap[mid] = incoming;
        }
    }
    let _fAlto = 0, _fMedio = 0, _fBajo = 0;
    for (const risk of Object.values(_formRiskMap)) {
        if (risk === 'R_ALTO') _fAlto++;
        else if (risk === 'R_MEDIO') _fMedio++;
        else _fBajo++;
    }
    const _fTotal = _fAlto + _fMedio + _fBajo;

    // ── Badge row (uses form-level counts, not raw alert counts) ──────────────
    const riskBadgeParts = [];
    if (_fAlto  > 0) riskBadgeParts.push(`<span style="font-size:0.7rem;color:#E05252;font-weight:600;">&#9679; ${_fAlto} alto</span>`);
    if (_fMedio > 0) riskBadgeParts.push(`<span style="font-size:0.7rem;color:#F07030;font-weight:600;">&#9679; ${_fMedio} medio</span>`);
    if (_fBajo  > 0) riskBadgeParts.push(`<span style="font-size:0.7rem;color:#D4A017;font-weight:600;">&#9679; ${_fBajo} bajo</span>`);
    const riskBadgesHtml = riskBadgeParts.length > 0
        ? `&nbsp;&nbsp;${riskBadgeParts.join('&nbsp; ')}`
        : '';

    // ── Bar: risk-colored segments proportional to form counts ────────────────
    let barInnerHtml;
    if (_fTotal > 0 && pct > 0) {
        const _aW = (_fAlto  / _fTotal) * pct;
        const _mW = (_fMedio / _fTotal) * pct;
        const _bW = (_fBajo  / _fTotal) * pct;
        barInnerHtml = [
            _aW > 0 ? `<div style="width:${_aW.toFixed(2)}%;background:#DC2626;height:100%;"></div>` : '',
            _mW > 0 ? `<div style="width:${_mW.toFixed(2)}%;background:#EA580C;height:100%;"></div>` : '',
            _bW > 0 ? `<div style="width:${_bW.toFixed(2)}%;background:#CA8A04;height:100%;"></div>` : '',
        ].join('');
    } else {
        barInnerHtml = pct > 0
            ? `<div style="width:${pct.toFixed(1)}%;background:${barColor};height:100%;min-width:4px;"></div>`
            : '';
    }

    // ── Risk legend (% de formularios por nivel) ──────────────────────────────
    const riskLegendHtml = _fTotal > 0 ? (() => {
        const _aP = Math.round(_fAlto  / _fTotal * 100);
        const _mP = Math.round(_fMedio / _fTotal * 100);
        const _bP = Math.round(_fBajo  / _fTotal * 100);
        return `<div style="display:flex;justify-content:flex-end;font-size:0.62rem;color:var(--muted,#888);margin-top:3px;gap:0.6rem;">
            ${_fAlto  > 0 ? `<span style="color:#DC2626;font-weight:600;">${_aP}% alto</span>`   : ''}
            ${_fMedio > 0 ? `<span style="color:#EA580C;font-weight:600;">${_mP}% medio</span>` : ''}
            ${_fBajo  > 0 ? `<span style="color:#CA8A04;font-weight:600;">${_bP}% bajo</span>`   : ''}
        </div>`;
    })() : '';

    // ── Candidate avatars ──────────────────────────────────────────────────────
    const CAND_COLORS = ['#C9A84C', '#2563EB', '#16A34A'];
    const CAND_IMGS = {
        0:   '/static/img/logopmsn.png',
        1:   '/static/img/egm.png',
        100: '/static/img/sara.png',
    };
    const candidateAvatars = [...candidateTotals.entries()]
        .sort(([a], [b]) => a - b)
        .map(([slot, { votes, actas }], idx) => {
            const color = CAND_COLORS[idx % CAND_COLORS.length];
            const imgSrc = CAND_IMGS[slot];
            const nameLabel = slot === 0 ? 'Lista' : `Cand. ${slot}`;
            const votesLabel = votes > 0 ? formatNumber(votes) : '—';
            const actasLabel = actas > 0 ? `${actas} acta${actas !== 1 ? 's' : ''}` : 'sin datos';
            const avatarHtml = imgSrc
                ? `<img src="${imgSrc}" alt="${nameLabel}" style="width:52px;height:52px;border-radius:50%;${slot===0?'object-fit:contain;padding:4px;background:#fff;':'object-fit:cover;'}border:2px solid ${color};box-shadow:0 2px 8px ${color}55;">`
                : `<div style="width:52px;height:52px;border-radius:50%;background:${color};display:flex;align-items:center;justify-content:center;font-weight:800;font-size:0.8rem;color:#fff;box-shadow:0 2px 8px ${color}66;">C${slot}</div>`;
            return `
                <div style="display:flex;flex-direction:column;align-items:center;gap:0.25rem;min-width:72px;">
                    ${avatarHtml}
                    <div style="font-size:0.7rem;font-weight:600;color:var(--text,#111);text-align:center;">${nameLabel}</div>
                    <div style="font-size:0.82rem;font-weight:700;color:${color};">${votesLabel}</div>
                    <div style="font-size:0.62rem;color:var(--muted,#888);">${actasLabel}</div>
                </div>`;
        }).join('');

    const mesasHtml = `
        <div style="border-top:1px solid var(--border-light,#eee); margin-top:0.6rem; padding-top:0.75rem;">
            <div style="display:flex;justify-content:space-around;flex-wrap:wrap;gap:0.5rem;margin-bottom:0.75rem;">
                ${candidateAvatars}
            </div>
            <div style="overflow-x:auto;">
                <table style="width:100%; border-collapse:collapse; min-width:300px;">
                    <thead>
                        <tr style="border-bottom:2px solid #ddd; font-size:0.72rem; color:var(--muted,#666);">
                            <th style="text-align:left; padding:0.3rem 0.75rem; font-weight:600;">Candidato</th>
                            <th style="text-align:right; padding:0.3rem 0.75rem; font-weight:600;">Votos (total OCR)</th>
                            <th style="text-align:right; padding:0.3rem 0.75rem; font-weight:600;">Actas</th>
                        </tr>
                    </thead>
                    <tbody>${candidateRows}</tbody>
                </table>
                ${allForms.length === 0 ? '<div style="text-align:center;color:var(--muted,#888);font-size:0.8rem;padding:0.75rem 0;">Sin actas procesadas</div>' : ''}
            </div>
        </div>`;

    container.innerHTML = `
        <div style="background: var(--card-bg, #fff); border-radius: 12px; padding: 1.2rem; border: 1px solid var(--border, #e5e5e5);">
            <div style="display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 0.5rem;">
                <div>
                    <span style="display:flex; align-items:center; gap:0.5rem; font-family:'Cinzel','Copperplate Gothic Bold',fantasy; font-weight:600; font-size:0.85rem; letter-spacing:0.07em; text-transform:uppercase; color:#fff; background:#1E224F; border-bottom:2px solid #E93C55; border-radius:6px 6px 0 0; padding:0.5rem 0.8rem; margin:-1.2rem -1.2rem 0.8rem -1.2rem;">
                        <img src="/static/img/logopmsn.png" alt="PMSN" height="22" style="object-fit:contain; object-fit:contain;">
                        Umbral PMSN — Movimiento Salvación Nacional
                    </span>
                    ${formsHtml}
                </div>
                <div style="text-align:right; white-space:nowrap;">
                    <span style="font-size: 0.85rem; color: var(--muted, #666);">${formatNumber(pmsnVotes)} / ${formatNumber(PMSN_THRESHOLD_TARGET)} votos${riskBadgesHtml}</span>
                </div>
            </div>
            <div style="position:relative; width:100%; padding-top:22px; margin-bottom:0.2rem;">
                <!-- Label umbral encima -->
                <div style="position:absolute; top:0; left:${thresholdPct.toFixed(1)}%; transform:translateX(-50%); display:flex; flex-direction:column; align-items:center; gap:1px; z-index:2;">
                    <span style="background:#DC2626; color:#fff; font-size:0.62rem; font-weight:700; padding:1px 5px; border-radius:3px; white-space:nowrap;">630.000 umbral</span>
                    <span style="color:#DC2626; font-size:0.7rem; line-height:1;">▼</span>
                </div>
                <!-- Barra con segmentos de riesgo dentro -->
                <div style="position:relative; width:100%; background:#E5E7EB; border-radius:8px; height:24px; overflow:hidden; display:flex;">
                    ${barInnerHtml}
                </div>
                <!-- Línea roja umbral (z-index alto) -->
                <div style="position:absolute; bottom:0; left:${thresholdPct.toFixed(1)}%; transform:translateX(-50%); width:4px; height:24px; background:#DC2626; z-index:3; border-radius:2px; box-shadow:0 0 4px rgba(220,38,38,0.6);"></div>
            </div>
            ${riskLegendHtml}
            ${mesasHtml}
        </div>
    `;
}

function renderPMSNRuleSemaphore(data) {
    const container = document.getElementById('pmsn-rule-semaphore');
    if (!container) return;

    const ruleCounts = data.rule_counts || {};
    const cards = Object.entries(PMSN_RULE_META).map(([ruleId, meta]) => {
        const count = ruleCounts[ruleId] || 0;
        const bgColor = count > 0 ? meta.color : '#9CA3AF';
        return `
            <div onclick="filterPMSNAlerts('${ruleId}', null)" style="background: var(--card-bg, #fff); border-radius: 10px; padding: 0.8rem; border: 1px solid var(--border, #e5e5e5); cursor: pointer; text-align: center; transition: transform 0.15s;" onmouseover="this.style.transform='scale(1.03)'" onmouseout="this.style.transform='scale(1)'">
                <div style="width: 36px; height: 36px; border-radius: 50%; background: ${bgColor}; margin: 0 auto 0.4rem; display: flex; align-items: center; justify-content: center;">
                    <span style="color: #fff; font-weight: 700; font-size: 0.9rem;">${count}</span>
                </div>
                <div style="font-size: 0.7rem; color: var(--text, #111); font-weight: 500; line-height: 1.2;">${ruleId}</div>
                <div style="font-size: 0.65rem; color: var(--muted, #666); margin-top: 2px; line-height: 1.2;">${meta.label}</div>
            </div>
        `;
    }).join('');

    container.innerHTML = `
        <div style="background: var(--card-bg, #fff); border-radius: 12px; padding: 1.2rem; border: 1px solid var(--border, #e5e5e5); margin-bottom: 1rem;">
            <div style="font-weight: 600; font-size: 0.95rem; color: var(--text, #111); margin-bottom: 0.8rem;">Semáforo Reglas PMSN <span style="font-weight: 400; font-size: 0.8rem; color: var(--muted, #666);">(${data.alerts_count || 0} alertas en ${data.total_forms || 0} formularios)</span></div>
            <div style="display: grid; grid-template-columns: repeat(auto-fill, minmax(100px, 1fr)); gap: 0.6rem;">
                ${cards}
            </div>
        </div>
    `;
}

function sumPmsnVotes(partidos) {
    let total = 0;
    for (const p of partidos) {
        if (isPmsnParty(p.party_name)) total += (p.votes || 0);
    }
    return total;
}

function groupAlertsByMesa(alerts) {
    const map = {};
    for (const a of alerts) {
        const key = a.mesa_id || '';
        if (!map[key]) map[key] = [];
        map[key].push(a);
    }
    return map;
}

function classifyPmsnMesas(pmsnData) {
    const capitals = new Set(['BOGOTA', 'MEDELLIN', 'CALI', 'BARRANQUILLA', 'CARTAGENA',
        'BUCARAMANGA', 'CUCUTA', 'PEREIRA', 'MANIZALES', 'IBAGUE', 'SANTA MARTA',
        'VILLAVICENCIO', 'PASTO', 'MONTERIA', 'NEIVA', 'ARMENIA', 'POPAYAN',
        'SINCELEJO', 'VALLEDUPAR', 'TUNJA', 'RIOHACHA', 'QUIBDO', 'FLORENCIA',
        'YOPAL', 'MOCOA', 'ARAUCA', 'LETICIA', 'SAN JOSE DEL GUAVIARE',
        'MITU', 'PUERTO CARRENO', 'INIRIDA', 'SAN ANDRES']);

    // Use all e14LiveData.forms as the primary source (all ~340 actas).
    // Enrich with forms_pmsn lookup (has pmsn_votes, risk_level, has_alert per form).
    const allForms = window.e14LiveData?.forms || [];
    // Use resolvedData (passed directly) so this works even before window.e14Data is set
    const formsPmsnArr = (pmsnData || {}).forms_pmsn || window.e14Data?.pmsnAlerts?.forms_pmsn || [];
    const formsPmsnLookup = {};
    for (const fp of formsPmsnArr) { formsPmsnLookup[fp.mesa_id] = fp; }
    // Fall back to forms_pmsn if e14LiveData not yet loaded
    const forms = allForms.length ? allForms : formsPmsnArr;
    const alertsByMesa = groupAlertsByMesa(
        window.e14Data?.pmsnAlerts?.alerts || []
    );
    const mesas = [];
    let sinDatos = 0;

    for (const f of forms) {
        const totalVotos = f.total_votos || f.resumen?.total_votos_validos || 0;
        if (totalVotos <= 0) { sinDatos++; continue; }
        const mesaIdKey = f.mesa_id || f.id;
        const fpEntry = formsPmsnLookup[mesaIdKey];
        const pmsnVotes = (f.pmsn_votes != null)
            ? f.pmsn_votes
            : (fpEntry?.pmsn_votes != null ? fpEntry.pmsn_votes : sumPmsnVotes(f.partidos || []));
        const pct = (pmsnVotes / totalVotos) * 100;
        const muni = (f.municipio || f.header?.municipio || '')
            .toUpperCase().replace(/[^A-Z ]/g, '').trim();
        const isCapital = capitals.has(muni);
        const threshold = isCapital ? 8 : 2.5;
        const mesaId = f.mesa_id || f.id;
        const hasAlertFlag = f.has_alert ?? fpEntry?.has_alert;
        const alertas = (hasAlertFlag != null)
            ? (hasAlertFlag ? [1] : [])
            : (alertsByMesa[mesaId] || []);
        const dept = (f.departamento || f.header?.departamento || '').toUpperCase().trim();
        const zona = f.zona_cod || f.header?.zona || '';
        const puesto = f.puesto_cod || f.header?.puesto || '';
        const mesaNum = f.mesa_num || f.header?.mesa || '';
        const riskLevel = f.risk_level || '';
        const formId = f.form_id || f.id || null;
        mesas.push({
            mesaId, mesaNum, pmsnVotes, totalVotos, pct, muni, dept, zona, puesto,
            riskLevel, formId, isCapital,
            isBuena: pct >= threshold,
            isMala: pct < 1,
            hasAlert: alertas.length > 0,
            alertCount: alertas.length,
        });
    }
    return { mesas, sinDatos };
}

function renderPmsnMesaRow(m) {
    const alertIcon = m.hasAlert
        ? `<span title="${m.alertCount} alerta(s)" style="color: #DC2626;">&#9888; ${m.alertCount}</span>`
        : '<span style="color: #16A34A;">&#10003;</span>';
    const _inc = (allIncidents || []).find(i => String(i.mesa_id) === String(m.mesaId));
    const rowId = _inc ? `#${_inc.id}` : (m.formId != null ? `#${m.formId}` : '—');
    return `<tr style="border-bottom: 1px solid #eee; font-size: 0.78rem;">
        <td style="padding: 0.3rem 0.5rem; font-family:monospace; color:var(--muted,#888); font-size:0.72rem; white-space:nowrap;">${rowId}</td>
        <td style="padding: 0.3rem 0.5rem;">${escapeHtml(m.mesaNum || String(m.mesaId))}</td>
        <td style="padding: 0.3rem 0.5rem;">${escapeHtml(m.muni)}</td>
        <td style="text-align: right; padding: 0.3rem 0.5rem;">${m.pmsnVotes.toLocaleString()}</td>
        <td style="text-align: right; padding: 0.3rem 0.5rem;">${m.totalVotos.toLocaleString()}</td>
        <td style="text-align: right; padding: 0.3rem 0.5rem;">${m.pct.toFixed(1)}%</td>
        <td style="text-align: center; padding: 0.3rem 0.5rem;">${alertIcon}</td>
    </tr>`;
}

function renderPmsnExpandableSection(id, title, mesas, color) {
    const maxRows = 50;
    const shown = mesas.slice(0, maxRows);
    const remaining = mesas.length - maxRows;
    const rows = shown.map(m => renderPmsnMesaRow(m)).join('');
    return `
        <div style="margin-bottom: 0.5rem;">
            <div onclick="togglePmsnSection('${id}')" style="cursor: pointer; padding: 0.5rem 0.8rem; background: ${color}; border-radius: 6px; display: flex; justify-content: space-between; align-items: center;">
                <span style="font-weight: 600; font-size: 0.85rem;">${title} (${mesas.length})</span>
                <span id="${id}-arrow" style="font-size: 0.7rem;">&#9660;</span>
            </div>
            <div id="${id}" style="display: none; max-height: 300px; overflow-y: auto;">
                <table style="width: 100%; border-collapse: collapse; margin-top: 0.3rem;">
                    <thead><tr style="border-bottom: 2px solid #ddd; font-size: 0.7rem; color: var(--muted);">
                        <th style="text-align: left; padding: 0.3rem 0.5rem;">ID</th>
                        <th style="text-align: left; padding: 0.3rem 0.5rem;">Mesa</th>
                        <th style="text-align: left; padding: 0.3rem 0.5rem;">Municipio</th>
                        <th style="text-align: right; padding: 0.3rem 0.5rem;">Votos PMSN</th>
                        <th style="text-align: right; padding: 0.3rem 0.5rem;">Total</th>
                        <th style="text-align: right; padding: 0.3rem 0.5rem;">%</th>
                        <th style="text-align: center; padding: 0.3rem 0.5rem;">Alerta</th>
                    </tr></thead>
                    <tbody>${rows}</tbody>
                </table>
                ${remaining > 0 ? `<div style="text-align: center; font-size: 0.75rem; color: var(--muted); padding: 0.4rem;">... y ${remaining} más</div>` : ''}
            </div>
        </div>`;
}

function renderPmsnSummaryCards(buenas, malas, top, sinDatos, topVotes) {
    return `
        <div style="display: grid; grid-template-columns: repeat(auto-fill, minmax(140px, 1fr)); gap: 0.8rem; margin-bottom: 1rem;">
            <div style="text-align: center; padding: 0.8rem; background: rgba(137,201,127,0.15); border: 1px solid rgba(137,201,127,0.4); border-radius: 8px; cursor: pointer;" onclick="togglePmsnSection('pmsn-buenas')">
                <div style="font-size: 1.4rem; font-weight: 700; color: #2c6b2c;">${formatNumber(buenas)}</div>
                <div style="font-size: 0.75rem; color: #2c6b2c; font-weight: 600;">Mesas Buenas</div>
                <div style="font-size: 0.65rem; color: #3a8a3a;">Capital ≥8% · Otro ≥2.5%</div>
            </div>
            <div style="text-align: center; padding: 0.8rem; background: rgba(233,60,85,0.08); border: 1px solid rgba(233,60,85,0.3); border-radius: 8px; cursor: pointer;" onclick="togglePmsnSection('pmsn-malas')">
                <div style="font-size: 1.4rem; font-weight: 700; color: #E93C55;">${formatNumber(malas)}</div>
                <div style="font-size: 0.75rem; color: #E93C55; font-weight: 600;">Mesas Malas</div>
                <div style="font-size: 0.65rem; color: #c9284a;">&lt;1% votos PMSN</div>
            </div>
            <div style="text-align: center; padding: 0.8rem; background: rgba(244,189,49,0.15); border: 1px solid rgba(244,189,49,0.4); border-radius: 8px; cursor: pointer;" onclick="togglePmsnSection('pmsn-top')">
                <div style="font-size: 1.4rem; font-weight: 700; color: #8c6a00;">${formatNumber(top)}</div>
                <div style="font-size: 0.75rem; color: #8c6a00; font-weight: 600;">Top Mesas PMSN</div>
                <div style="font-size: 0.65rem; color: #a07c00;">${formatNumber(topVotes)} votos acumulados</div>
            </div>
            <div style="text-align: center; padding: 0.8rem; background: rgba(30,34,79,0.06); border: 1px solid rgba(30,34,79,0.15); border-radius: 8px;">
                <div style="font-size: 1.4rem; font-weight: 700; color: #1E224F;">${formatNumber(sinDatos)}</div>
                <div style="font-size: 0.75rem; color: #1E224F; font-weight: 600;">Sin datos</div>
                <div style="font-size: 0.65rem; color: #4a5070;">Total votos = 0</div>
            </div>
        </div>`;
}

window.togglePmsnSection = function(id) {
    const el = document.getElementById(id);
    if (!el) return;
    const arrow = document.getElementById(id + '-arrow');
    if (el.style.display === 'none') {
        el.style.display = 'block';
        if (arrow) arrow.innerHTML = '&#9650;';
    } else {
        el.style.display = 'none';
        if (arrow) arrow.innerHTML = '&#9660;';
    }
};

function renderPMSNMesasClassification(data) {
    const container = document.getElementById('pmsn-mesas-classification');
    if (!container) return;

    const { mesas, sinDatos } = classifyPmsnMesas();

    const buenasList = mesas.filter(m => m.isBuena)
        .sort((a, b) => b.pct - a.pct);
    const malasList = mesas.filter(m => m.isMala)
        .sort((a, b) => a.pct - b.pct);

    mesas.sort((a, b) => b.pmsnVotes - a.pmsnVotes);
    const topList = mesas.slice(0, 1000);
    const topVotes = topList.reduce((s, m) => s + m.pmsnVotes, 0);

    const cards = renderPmsnSummaryCards(
        buenasList.length, malasList.length,
        topList.length, sinDatos, topVotes
    );

    const buenasSection = renderPmsnExpandableSection(
        'pmsn-buenas', 'Mesas Buenas', buenasList, 'rgba(137,201,127,0.15)'
    );
    const malasSection = renderPmsnExpandableSection(
        'pmsn-malas', 'Mesas Malas', malasList, 'rgba(233,60,85,0.08)'
    );
    const topSection = renderPmsnExpandableSection(
        'pmsn-top', 'Top Mesas por Votos PMSN', topList, 'rgba(244,189,49,0.15)'
    );

    container.innerHTML = `
        <div style="background: var(--card-bg, #fff); border-radius: 12px; padding: 1.2rem; border: 1px solid var(--border, #e5e5e5); margin-bottom: 1rem;">
            <div style="display:flex; align-items:center; gap:0.5rem; font-family:'Cinzel','Copperplate Gothic Bold',fantasy; font-weight:600; font-size:0.85rem; letter-spacing:0.07em; text-transform:uppercase; color:#fff; background:#1E224F; border-bottom:2px solid #E93C55; border-radius:6px 6px 0 0; padding:0.5rem 0.8rem; margin:-1.2rem -1.2rem 0.8rem -1.2rem;">
                <img src="/static/img/logopmsn.png" alt="PMSN" height="22" style="object-fit:contain; object-fit:contain;">
                Clasificación de Mesas PMSN
            </div>
            ${cards}
            ${buenasSection}
            ${malasSection}
            ${topSection}
        </div>
    `;
}

function renderPMSNAlertsTable(alerts) {
    const container = document.getElementById('pmsn-alerts-table-container');
    if (!container) return;

    // Store full alerts for filtering
    window._pmsnAllAlerts = alerts;

    const riskFilters = Object.entries(PMSN_RISK_COLORS).map(([risk, color]) => {
        const label = risk === 'R_ALTO' ? 'Alto' : risk === 'R_MEDIO' ? 'Medio' : 'Bajo';
        return `<button onclick="filterPMSNAlerts(null, '${risk}')" style="padding: 0.3rem 0.7rem; border-radius: 6px; border: 1px solid ${color}; background: transparent; color: ${color}; font-size: 0.75rem; font-weight: 600; cursor: pointer;">${label}</button>`;
    }).join('');

    container.innerHTML = `
        <div style="background: var(--card-bg, #fff); border-radius: 12px; padding: 1.2rem; border: 1px solid var(--border, #e5e5e5);">
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.8rem; flex-wrap: wrap; gap: 0.5rem;">
                <span style="font-weight: 600; font-size: 0.95rem; color: var(--text, #111);">Alertas PMSN <span id="pmsn-alerts-shown" style="font-weight: 400; font-size: 0.8rem; color: var(--muted, #666);">(${alerts.length})</span></span>
                <div style="display: flex; gap: 0.4rem; align-items: center;">
                    <button onclick="filterPMSNAlerts(null, null)" style="padding: 0.3rem 0.7rem; border-radius: 6px; border: 1px solid var(--border, #ccc); background: transparent; color: var(--text, #333); font-size: 0.75rem; cursor: pointer;">Todas</button>
                    ${riskFilters}
                </div>
            </div>
            <div style="max-height: 350px; overflow-y: auto;">
                <table style="width: 100%; border-collapse: collapse; font-size: 0.8rem;">
                    <thead>
                        <tr style="border-bottom: 2px solid var(--border, #e5e5e5); text-align: left;">
                            <th style="padding: 0.4rem;">Regla</th>
                            <th style="padding: 0.4rem; white-space: nowrap;">Fecha</th>
                            <th style="padding: 0.4rem; white-space: nowrap;">Hora</th>
                            <th style="padding: 0.4rem; white-space: nowrap;">Corp.</th>
                            <th style="padding: 0.4rem;">Riesgo</th>
                            <th style="padding: 0.4rem;">Mesa</th>
                            <th style="padding: 0.4rem;">Depto</th>
                            <th style="padding: 0.4rem;">Municipio</th>
                            <th style="padding: 0.4rem;">Descripción</th>
                        </tr>
                    </thead>
                    <tbody id="pmsn-alerts-tbody">
                        ${_renderPMSNAlertRows(alerts)}
                    </tbody>
                </table>
            </div>
        </div>
    `;
}

function _renderPMSNAlertRows(alerts) {
    if (!alerts || alerts.length === 0) {
        return '<tr><td colspan="9" style="text-align: center; padding: 1rem; color: var(--muted, #666);">Sin alertas PMSN</td></tr>';
    }

    return alerts.slice(0, 200).map(a => {
        const color = PMSN_RISK_COLORS[a.risk_type] || '#9CA3AF';
        const riskLabel = a.risk_type === 'R_ALTO' ? 'Alto' : a.risk_type === 'R_MEDIO' ? 'Medio' : 'Bajo';
        const mesaId = a.mesa_id || a.details?.mesa_id || '—';
        const _dt = a.processed_at ? new Date(a.processed_at) : null;
        const _fecha = _dt ? _dt.toLocaleDateString('es-CO', {day: '2-digit', month: '2-digit', year: 'numeric'}) : '—';
        const _hora  = _dt ? _dt.toLocaleTimeString('es-CO', {hour: '2-digit', minute: '2-digit'}) : '—';
        const corp = (a.corporacion || '').toUpperCase();
        const corpLabel = corp === 'SENADO' ? 'SEN' : corp === 'CAMARA' ? 'CAM' : (corp.slice(0, 3) || '—');
        const corpColor = corp === 'SENADO' ? '#6366F1' : corp === 'CAMARA' ? '#0EA5E9' : '#9CA3AF';
        return `
            <tr style="border-bottom: 1px solid var(--border, #f0f0f0);">
                <td style="padding: 0.4rem; font-weight: 600;">${a.rule_id}</td>
                <td style="padding: 0.4rem; font-size: 0.75rem; white-space: nowrap;">${_fecha}</td>
                <td style="padding: 0.4rem; font-size: 0.75rem; white-space: nowrap;">${_hora}</td>
                <td style="padding: 0.4rem;"><span style="display: inline-block; padding: 0.15rem 0.45rem; border-radius: 4px; background: ${corpColor}; color: #fff; font-size: 0.7rem; font-weight: 600;">${corpLabel}</span></td>
                <td style="padding: 0.4rem;"><span style="display: inline-block; padding: 0.15rem 0.5rem; border-radius: 4px; background: ${color}; color: #fff; font-size: 0.7rem; font-weight: 600;">${riskLabel}</span></td>
                <td style="padding: 0.4rem; font-family: monospace; font-size: 0.75rem;">${mesaId}</td>
                <td style="padding: 0.4rem;">${a.departamento || '—'}</td>
                <td style="padding: 0.4rem;">${a.municipio || '—'}</td>
                <td style="padding: 0.4rem; max-width: 250px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;" title="${(a.description || '').replace(/"/g, '&quot;')}">${a.description || '—'}</td>
            </tr>
        `;
    }).join('');
}

function filterPMSNAlerts(ruleId, riskType) {
    const allAlerts = window._pmsnAllAlerts || [];
    let filtered = allAlerts;

    if (ruleId) {
        filtered = filtered.filter(a => a.rule_id === ruleId);
    }
    if (riskType) {
        filtered = filtered.filter(a => a.risk_type === riskType);
    }

    const tbody = document.getElementById('pmsn-alerts-tbody');
    if (tbody) {
        tbody.innerHTML = _renderPMSNAlertRows(filtered);
    }

    const shown = document.getElementById('pmsn-alerts-shown');
    if (shown) {
        const label = ruleId || (riskType ? riskType.replace('R_', '') : 'todas');
        shown.textContent = `(${filtered.length} — ${label})`;
    }
}


/**
 * Renderiza gráfico de torta de votos por partido.
 * @param {PartyVote[]} votes
 */
function renderPartyChart(votes) {
    const ctx = document.getElementById('party-chart')?.getContext('2d');
    if (!ctx) return;

    if (partyChart) partyChart.destroy();

    // Aggregate votes by party
    const partyVotes = {};
    votes.forEach(v => {
        const party = v.party_name || 'Independiente';
        partyVotes[party] = (partyVotes[party] || 0) + (v.total_votes || 0);
    });

    const labels = Object.keys(partyVotes).slice(0, 8);
    const data = labels.map(l => partyVotes[l]);
    const colors = generateGoldPalette(labels.length);

    partyChart = new Chart(ctx, {
        type: 'pie',
        data: {
            labels: labels.map(l => truncateText(l, 20)),
            datasets: [{
                data: data,
                backgroundColor: colors,
                borderColor: '#FFFFFF',
                borderWidth: 2
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    position: 'right',
                    labels: {
                        color: '#111111',
                        padding: 10,
                        font: { size: 10 },
                        usePointStyle: true,
                        pointStyle: 'circle'
                    }
                },
                tooltip: {
                    callbacks: {
                        label: function(context) {
                            const total = context.dataset.data.reduce((a, b) => a + b, 0);
                            const value = context.raw;
                            const percentage = ((value / total) * 100).toFixed(1);
                            const partyName = labels[context.dataIndex];
                            const partyData = votes.find(v => (v.party_name || 'Independiente') === partyName);
                            const lines = [`${context.label}: ${formatNumber(value)} (${percentage}%)`];
                            if (partyData && (partyData.votes_high_risk || partyData.votes_medium_risk)) {
                                lines.push(`  Alto riesgo: ${formatNumber(partyData.votes_high_risk || 0)}`);
                                lines.push(`  Riesgo medio: ${formatNumber(partyData.votes_medium_risk || 0)}`);
                                lines.push(`  Bajo riesgo: ${formatNumber(partyData.votes_low_risk || 0)}`);
                            }
                            return lines;
                        }
                    }
                }
            }
        }
    });
}

/**
 * Renderiza gráfico de barras apiladas de riesgo por partido.
 * @param {PartyVote[]} votes
 */
function renderRiskDonutChart(votes) {
    const ctx = document.getElementById('risk-donut-chart')?.getContext('2d');
    if (!ctx) return;

    if (riskChart) riskChart.destroy();

    // Top parties with any risk data
    const parties = votes
        .filter(v => (v.votes_high_risk || 0) + (v.votes_medium_risk || 0) + (v.votes_low_risk || 0) > 0)
        .slice(0, 10);

    if (parties.length === 0) {
        ctx.canvas.parentElement.style.display = 'none';
        return;
    }
    ctx.canvas.parentElement.style.display = '';

    const labels = parties.map(p => truncateText(p.party_name || 'Sin partido', 18));

    riskChart = new Chart(ctx, {
        type: 'bar',
        data: {
            labels: labels,
            datasets: [
                {
                    label: `Alto (<${OCR_HIGH_RISK}%)`,
                    data: parties.map(p => p.votes_high_risk || 0),
                    backgroundColor: '#C0253A',
                },
                {
                    label: `Medio (${OCR_HIGH_RISK}-${OCR_MEDIUM_RISK}%)`,
                    data: parties.map(p => p.votes_medium_risk || 0),
                    backgroundColor: '#D4A017',
                },
                {
                    label: `Bajo (≥${OCR_MEDIUM_RISK}%)`,
                    data: parties.map(p => p.votes_low_risk || 0),
                    backgroundColor: '#1E7D4F',
                },
            ]
        },
        options: {
            indexAxis: 'y',
            responsive: true,
            maintainAspectRatio: false,
            scales: {
                x: {
                    stacked: true,
                    ticks: { color: '#444444', font: { size: 9 } },
                    grid: { color: 'rgba(0,0,0,0.08)' },
                },
                y: {
                    stacked: true,
                    ticks: { color: '#111111', font: { size: 9 } },
                    grid: { display: false },
                },
            },
            plugins: {
                legend: {
                    position: 'top',
                    labels: {
                        color: '#111111',
                        padding: 8,
                        font: { size: 9 },
                        usePointStyle: true,
                        pointStyle: 'circle',
                        boxWidth: 8,
                    }
                },
                tooltip: {
                    callbacks: {
                        label: function(context) {
                            const value = context.raw || 0;
                            const party = parties[context.dataIndex];
                            const total = (party.votes_high_risk || 0)
                                + (party.votes_medium_risk || 0)
                                + (party.votes_low_risk || 0);
                            const pct = total > 0 ? ((value / total) * 100).toFixed(1) : '0';
                            return `${context.dataset.label}: ${formatNumber(value)} (${pct}%)`;
                        }
                    }
                }
            }
        }
    });
}

/**
 * Renderiza tabla de partidos con votos, confianza y riesgo.
 * @param {PartyVote[]} votes
 */
function renderPartyList(votes) {
    const tbody = document.getElementById('party-list-tbody');
    const countEl = document.getElementById('parties-count');
    const tableCountEl = document.getElementById('table-count');
    if (!tbody) return;

    // Update E-14 form count in section header
    const totalForms = window.e14Data?.stats?.total_forms
        ?? window.e14Data?.pmsnAlerts?.total_forms
        ?? null;
    if (tableCountEl && totalForms !== null) {
        tableCountEl.textContent = `${totalForms} E-14s procesados`;
    }

    // Vote types that are annotations, not real parties
    const SKIP_NAMES = new Set(['VOTO PREFERENTE']);

    // Merge entries with the same cleaned name (backend aggregates by raw name)
    const merged = new Map(); // cleanedName → { total_votes, isPmsn }
    let totalVotes = 0;
    for (const p of votes) {
        const cleaned = cleanPartyName(p.party_name || p.party || '');
        if (!cleaned || SKIP_NAMES.has(cleaned)) continue;
        const v = p.total_votes || 0;
        if (!merged.has(cleaned)) {
            merged.set(cleaned, { total_votes: 0, isPmsn: isPmsnParty(p.party_name || '') });
        }
        merged.get(cleaned).total_votes += v;
        totalVotes += v;
    }

    const sorted = [...merged.entries()]
        .sort(([, a], [, b]) => b.total_votes - a.total_votes);

    if (countEl) countEl.textContent = `${sorted.length} partidos`;

    if (sorted.length === 0) {
        tbody.innerHTML = '<tr><td colspan="3" style="text-align: center; color: var(--muted);">No hay datos de partidos</td></tr>';
        return;
    }

    const rows = sorted.slice(0, 30).map(([name, data]) => {
        const votesVal = data.total_votes;
        const pct = totalVotes > 0 ? (votesVal / totalVotes * 100) : 0;
        const isPmsn = data.isPmsn;
        const rowStyle = isPmsn ? 'background: rgba(233,60,85,0.07); font-weight: 700; border-left: 3px solid #1E224F;' : '';
        const nameStyle = isPmsn ? 'padding-left: 0.4rem;' : '';
        const pmsnBadge = isPmsn ? ' <span style="font-size:0.6rem; background:#1E224F; color:#fff; padding:0.1rem 0.3rem; border-radius:3px; letter-spacing:0.05em;">PMSN</span>' : '';
        return `
            <tr style="${rowStyle}">
                <td style="${nameStyle}">${escapeHtml(name)}${pmsnBadge}</td>
                <td>${formatNumber(votesVal)}</td>
                <td>${pct.toFixed(2)}%</td>
            </tr>
        `;
    }).join('');

    const totalRow = `
        <tr style="border-top: 2px solid var(--border, #ddd); font-weight: 700; background: var(--panel, #f9f9f9);">
            <td>Total</td>
            <td>${formatNumber(totalVotes)}</td>
            <td>100%</td>
        </tr>
    `;

    tbody.innerHTML = rows + totalRow;
}

// renderOCRProblemsList and renderRiskDistributionChart removed (sections eliminated from dashboard)

/**
 * Genera HTML de barra apilada de riesgo (alto/medio/bajo).
 * @param {number} high - Votos alto riesgo
 * @param {number} med - Votos riesgo medio
 * @param {number} low - Votos bajo riesgo
 * @param {number} total - Total votos
 * @returns {string} HTML de la barra
 */
function buildRiskBar(high, med, low, total) {
    const hPct = (high / total * 100).toFixed(1);
    const mPct = (med / total * 100).toFixed(1);
    const lPct = (low / total * 100).toFixed(1);
    const title = `Alto: ${formatNumber(high)} (${hPct}%) | Medio: ${formatNumber(med)} (${mPct}%) | Bajo: ${formatNumber(low)} (${lPct}%)`;
    return `<div class="risk-stacked-bar" title="${title}" style="display:flex; height:14px; border-radius:3px; overflow:hidden; min-width:60px; cursor:help;">
        ${high > 0 ? `<div style="width:${hPct}%; background:#C0253A;"></div>` : ''}
        ${med > 0 ? `<div style="width:${mPct}%; background:#D4A017;"></div>` : ''}
        ${low > 0 ? `<div style="width:${lPct}%; background:#1E7D4F;"></div>` : ''}
    </div>`;
}

/**
 * Renderiza tabla de votos con barra de progreso y riesgo.
 * @param {PartyVote[]} votes
 */
function renderVotesTable(votes) {
    const tbody = document.getElementById('votes-tbody');
    const countEl = document.getElementById('table-count');

    if (!tbody) return;

    if (votes.length === 0) {
        tbody.innerHTML = '<tr><td colspan="6" style="text-align: center; color: var(--muted);">No hay datos disponibles</td></tr>';
        if (countEl) countEl.textContent = '0 registros';
        return;
    }

    const maxVotes = Math.max(...votes.map(v => v.total_votes || 0));

    tbody.innerHTML = votes.map(vote => {
        const confidence = vote.ocrConfidence || 85;
        const percentage = vote.percentage || 0;
        const barWidth = maxVotes > 0 ? ((vote.total_votes || 0) / maxVotes * 100) : 0;

        // Stacked risk bar
        const hr = vote.votes_high_risk || 0;
        const mr = vote.votes_medium_risk || 0;
        const lr = vote.votes_low_risk || 0;
        const riskTotal = hr + mr + lr;
        const riskBar = riskTotal > 0
            ? buildRiskBar(hr, mr, lr, riskTotal)
            : '<span class="risk-badge low">Bajo</span>';

        return `
            <tr>
                <td class="party-name" style="color: var(--text, #111111);">${escapeHtml(cleanPartyName(vote.party_name || vote.candidate_name) || '-')}</td>
                <td style="color: var(--text, #111111);">${formatNumber(vote.total_votes || 0)}</td>
                <td style="color: var(--text-secondary, #444444);">${percentage.toFixed(1)}%</td>
                <td class="vote-bar-cell">
                    <div class="vote-bar">
                        <div class="vote-bar-fill" style="width: ${barWidth}%; background: var(--accent, #1E7D4F);"></div>
                    </div>
                </td>
                <td title="Promedio de confianza OCR en ${vote.mesas_count || '?'} mesas" style="cursor: help; color: var(--text, #111111);">${confidence.toFixed(0)}%</td>
                <td>${riskBar}</td>
            </tr>
        `;
    }).join('');

    if (countEl) countEl.textContent = `${votes.length} registros`;

    // Add explanatory note about OCR confidence
    const table = tbody.closest('table');
    if (table) {
        let note = table.parentElement.querySelector('.ocr-confidence-note');
        if (!note) {
            note = document.createElement('div');
            note.className = 'ocr-confidence-note';
            note.style.cssText = 'font-size: 0.7rem; color: var(--muted); padding: 0.5rem 0; font-style: italic;';
            note.textContent = 'Legibilidad: promedio de lectura Tesseract. Alta legibilidad no descarta errores aritmeticos.';
            table.parentElement.appendChild(note);
        }
    }
}

// ============================================================
// ZONAS DE RIESGO TAB - Basado en E14 Anomalias OCR
// ============================================================

let selectedMunicipality = null;





window.selectMunicipality = function(key) {
    selectedMunicipality = key;
    renderMunicipalitiesList();
    renderMunicipalityDetailFromE14(key);
};


window.escalateMunicipality = function(key) {
    const [dept, muni] = (key || '').split('|');
    alert(`Escalando ${muni || key} (${dept || ''}) al equipo juridico.`);
};


let municipalitiesByFactor = {};



// Legacy functions for backward compatibility
window.viewMesaDetails = function(mesaId) {
    const mesa = allMesas.find(m => m.id === mesaId);
    if (mesa) {
        alert(`Detalles de ${mesa.mesaId}:\n\nUbicación: ${mesa.puesto}, ${mesa.muni}\nDirección: ${mesa.location}\nConfianza OCR: ${mesa.ocrConfidence?.toFixed(1) || '--'}%\nTotal votos: ${mesa.totalVotes}\nEstado: ${mesa.status}`);
    }
};

window.selectMesaForWitness = function(mesaId) {
    const mesa = allMesas.find(m => m.id === mesaId);
    if (mesa) {
        document.querySelector('[data-tab="llamar-testigo"]')?.click();
        setTimeout(() => {
            const select = document.getElementById('critical-mesa-select');
            if (select) {
                select.value = mesaId;
                onCriticalMesaSelect();
            }
        }, 100);
    }
};

// ============================================================
// (Llamar Testigo tab removed - see legacy file)
// ============================================================



// ============================================================
// TABLE SORTING
// ============================================================

function setupTableSorting() {
    document.querySelectorAll('.votes-table th.sortable').forEach(th => {
        th.addEventListener('click', () => {
            const sortKey = th.dataset.sort;
            sortVotesTable(sortKey, th);
        });
    });
}

let currentSort = { key: null, asc: true };

function sortVotesTable(key, th) {
    // Toggle sort direction
    if (currentSort.key === key) {
        currentSort.asc = !currentSort.asc;
    } else {
        currentSort.key = key;
        currentSort.asc = true;
    }

    // Update visual indicators
    document.querySelectorAll('.votes-table th.sortable').forEach(t => {
        t.classList.remove('sorted');
    });
    th.classList.add('sorted');
    th.querySelector('.sort-icon').textContent = currentSort.asc ? '↑' : '↓';

    // Sort the data
    const sortedVotes = [...getFilteredVotes()].sort((a, b) => {
        let valA, valB;

        switch (key) {
            case 'party':
                valA = (a.party_name || a.candidate_name || '').toLowerCase();
                valB = (b.party_name || b.candidate_name || '').toLowerCase();
                break;
            case 'votes':
                valA = a.total_votes || 0;
                valB = b.total_votes || 0;
                break;
            case 'percentage':
                valA = a.percentage || 0;
                valB = b.percentage || 0;
                break;
            case 'confidence':
                valA = a.ocrConfidence || 0;
                valB = b.ocrConfidence || 0;
                break;
            default:
                return 0;
        }

        if (valA < valB) return currentSort.asc ? -1 : 1;
        if (valA > valB) return currentSort.asc ? 1 : -1;
        return 0;
    });

    renderPartyList(sortedVotes);
}

// ============================================================
// REAL-TIME REFRESH
// ============================================================

function startRealTimeRefresh() {
    if (refreshInterval) clearInterval(refreshInterval);
}

async function manualRefresh() {
    const btn = document.getElementById('btn-actualizar');
    if (btn) { btn.disabled = true; btn.textContent = '↻ Actualizando...'; }
    try {
        await loadDashboardData();
    } finally {
        if (btn) { btn.disabled = false; btn.textContent = '↻ Actualizar'; }
    }
}

// ============================================================
// UTILITY FUNCTIONS
// ============================================================

function showLoading(show) {
    const overlay = document.getElementById('loading-overlay');
    if (overlay) {
        overlay.classList.toggle('active', show);
    }
}

function showError(message) {
    console.error(message);
    // Could show a toast notification here
}

function updateTimestamp() {
    const el = document.getElementById('last-update-time');
    if (el) {
        const now = new Date();
        el.textContent = now.toLocaleTimeString('es-CO', { hour: '2-digit', minute: '2-digit' });
    }
}

/**
 * @param {number|null|undefined} num
 * @returns {string}
 */
function formatNumber(num) {
    if (num === null || num === undefined) return '--';
    if (typeof num === 'string') return num;
    if (typeof num === 'number' && isNaN(num)) return '--';
    return new Intl.NumberFormat('es-CO').format(num);
}

function formatTime(date) {
    if (!date) return '--';
    return new Date(date).toLocaleTimeString('es-CO', { hour: '2-digit', minute: '2-digit' });
}

function truncateText(text, maxLength) {
    if (!text) return '';
    return text.length > maxLength ? text.substring(0, maxLength) + '...' : text;
}

function escapeHtml(text) {
    if (!text) return '';
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

/**
 * Normaliza nombres de partidos desde OCR (limpia ruido, mapea aliases).
 * @param {string} name - Nombre crudo del partido desde OCR
 * @returns {string} Nombre normalizado o '' si es ruido
 */
function cleanPartyName(name) {
    if (!name) return '';
    // Filter OCR mark artifacts before any other processing
    if (/__MARK__|^MARK\s*$/i.test(name)) return '';
    if (/^(?:ESCRUTINIO|MESA\s+DE|ACTA\s+E-?14|JURADOS|DELEGADOS|REGISTRADUR|ELECCIONES)/i.test(name.trim())) return '';

    // Strip recurring OCR noise: ballot-table annotations and checkbox OCR debris
    name = name
        .replace(/\s*\d*\s*VOTOS\s+POR\s+LA\s+AGRUPACI[OÓ]N\s+POLIT[IÍ]CA[\s\S]*/gi, '')
        .replace(/(\s+SELECTED)+/gi, '')
        .replace(/\s+\d{4}[\s\S]*/g, '')  // strip from first 4-digit party code onwards
        .trim();
    if (!name) return '';

    const PARTY_MAP = [
        [/PACTO\s*HIST[OÓ]RIC/i, 'PACTO HISTÓRICO'],
        [/LIBERAL\s+COLOMBIAN/i, 'PARTIDO LIBERAL COLOMBIANO'],
        [/CONSERVADOR\s+COLOMBIAN/i, 'PARTIDO CONSERVADOR COLOMBIANO'],
        [/CAMBIO\s+RADICAL/i, 'CAMBIO RADICAL'],
        [/CENTRO\s+DEMOCR[AÁ]TIC/i, 'CENTRO DEMOCRÁTICO'],
        [/SALVACI[OÓ]N\s+NACIONAL/i, 'MOV. DE SALVACIÓN NACIONAL'],
        [/ALIANZA\s+VERDE/i, 'ALIANZA VERDE - CENTRO ESPERANZA'],
        [/CENTRO\s+ESPERANZA/i, 'ALIANZA VERDE - CENTRO ESPERANZA'],
        [/COLOMBIA\s+JUSTA/i, 'MIRA - COLOMBIA JUSTA LIBRES'],
        [/METAPOL[IÍ]TIC/i, 'MOV. UNITARIO METAPOLÍTICO'],
        [/FUERZA\s+CIUDADANA/i, 'FUERZA CIUDADANA'],
        [/GENTE\s+NUEVA/i, 'MOV. GENTE NUEVA'],
        [/CENTRE\s*NEVA/i, 'MOV. GENTE NUEVA'],
        [/NUEVO\s+LIBERALISMO/i, 'NUEVO LIBERALISMO'],
        [/ESTAMOS\s+LISTAS/i, 'ESTAMOS LISTAS COLOMBIA'],
        [/MANDATO\s+AMBIENTA/i, 'MANDATO AMBIENTAL'],
        [/PARTIDO\s+COMUNES/i, 'PARTIDO COMUNES'],
        [/IND[IÍ]GENA\s+COLOMBIAN/i, 'PARTIDO INDÍGENA COLOMBIANO'],
        [/PARTIDO\s+DE\s+LA\s+U/i, 'PARTIDO DE LA U'],
        [/POLO\s+DEMOCR[AÁ]TIC/i, 'POLO DEMOCRÁTICO'],
        [/AUTORIDADES\s+IND[IÍ]GENAS/i, 'MOV. AUTORIDADES INDÍGENAS'],
        [/SALUD\s+SOS/i, 'SALUD SOS COLOMBIA'],
        [/DESDE\s+ABAJO/i, 'DEMOCRACIA DESDE ABAJO'],
        [/CABILDOS.*IND[IÍ]GENAS/i, 'ASOC. CABILDOS INDÍGENAS'],
        [/\bANICOL\b/i, 'ANICOL'],
        [/LISTA.*PREFERENT/i, 'VOTO PREFERENTE'],
        [/VOTO\s*PREFERENT/i, 'VOTO PREFERENTE'],
        [/PREFERENT/i, 'VOTO PREFERENTE'],
        [/\bMIRA\b/, 'MIRA'], [/\bMAIS\b/, 'MAIS'],
        [/\bADA\b/, 'ADA'],
    ];
    for (const [pat, c] of PARTY_MAP) { if (pat.test(name)) return c; }
    let cleaned = name
        .replace(/^(?:\d{1,5}[\s:;\-\.]*)+/, '')
        .replace(/^[^A-ZÁÉÍÓÚÑ]+/, '')
        .replace(/[\d\s\|\-\[\]\(\)]+$/, '')
        .replace(/[|¡\[\]_=\(\)]/g, '')
        .replace(/\s{2,}/g, ' ').trim();
    // Reject bare "COLOMBIA [letra/número]" — siempre es artefacto OCR de nombre más largo
    if (/^COLOMBIA(\s+[A-Z0-9]{1,3})*$/i.test(cleaned)) return '';
    for (const [pat, c] of PARTY_MAP) { if (pat.test(cleaned)) return c; }
    if (cleaned.length < 5) return '';
    if (cleaned.split(/\s+/).every(w => w.length <= 2)) return '';
    return cleaned;
}

function generateGoldPalette(count) {
    const baseColors = [
        'rgba(201, 162, 39, 0.8)',
        'rgba(212, 175, 55, 0.8)',
        'rgba(232, 212, 138, 0.8)',
        'rgba(139, 115, 85, 0.8)',
        'rgba(74, 124, 89, 0.8)',
        'rgba(91, 142, 255, 0.8)',
        'rgba(139, 58, 58, 0.7)',
        'rgba(212, 160, 23, 0.8)'
    ];

    const colors = [];
    for (let i = 0; i < count; i++) {
        colors.push(baseColors[i % baseColors.length]);
    }
    return colors;
}

// ============================================================
// CANDIDATOS EN SEGUIMIENTO
// ============================================================

// Candidatos cargados desde API (sin datos hardcoded)
/** @type {TrackedCandidate[]} */
let trackedCandidates = [];

function renderTrackedCandidates() {
    const grid = document.getElementById('candidates-tracking-grid');
    if (!grid) return;

    // If no data, show empty state
    const hasData = trackedCandidates.some(c => c.votes > 0);
    if (!hasData) {
        grid.innerHTML = '<div style="color: var(--muted); font-size: 0.85rem;">Sin datos de candidatos disponibles.</div>';
        return;
    }

    console.log('Rendering candidates:', trackedCandidates.map(c => ({name: c.name, votes: c.votes})));

    // Sort by votes descending
    const sortedCandidates = [...trackedCandidates].sort((a, b) => b.votes - a.votes);

    // Assign positions
    sortedCandidates.forEach((c, i) => {
        const original = trackedCandidates.find(tc => tc.id === c.id);
        if (original) original.position = i + 1;
    });

    // Sort by position for display
    const sortedForDisplay = [...trackedCandidates].sort((a, b) => (a.position || 99) - (b.position || 99));

    grid.innerHTML = sortedForDisplay.map(candidate => {
        const positionClass = candidate.position <= 3 ? 'top-3' : '';
        const cardClass = candidate.position === 1 ? 'leading' :
                         (candidate.position <= 3 ? '' :
                         (candidate.position >= 7 ? 'danger' : 'warning'));

        const trendIcon = candidate.trend === 'up' ? '↑' :
                         (candidate.trend === 'down' ? '↓' : '→');
        const trendClass = candidate.trend === 'up' ? 'trend-up' :
                          (candidate.trend === 'down' ? 'trend-down' : 'trend-stable');
        const trendText = candidate.trend === 'up' ? `+${Math.abs(candidate.trendValue)}%` :
                         (candidate.trend === 'down' ? `-${Math.abs(candidate.trendValue)}%` : 'Estable');

        const maxVotes = Math.max(...trackedCandidates.map(c => c.votes));
        const progressWidth = maxVotes > 0 ? (candidate.votes / maxVotes * 100) : 0;
        const candidateColor = candidate.color || '#C9A227';

        return `
            <div class="candidate-track-card ${cardClass}" style="border-left: 4px solid ${candidateColor}">
                <div class="candidate-track-header">
                    <div>
                        <div class="candidate-track-name">${escapeHtml(candidate.name)}</div>
                        <div class="candidate-track-party" style="color: ${candidateColor}">${escapeHtml(candidate.party)}</div>
                    </div>
                    <span class="candidate-track-position ${positionClass}">#${candidate.position || '--'}</span>
                </div>

                <div class="candidate-track-stats">
                    <div class="candidate-stat">
                        <div class="candidate-stat-value">${formatNumber(candidate.votes)}</div>
                        <div class="candidate-stat-label">Votos E-14</div>
                    </div>
                    <div class="candidate-stat">
                        <div class="candidate-stat-value">${candidate.percentage.toFixed(1)}%</div>
                        <div class="candidate-stat-label">Porcentaje</div>
                    </div>
                    <div class="candidate-stat">
                        <div class="candidate-stat-value">${formatNumber(candidate.mesas)}</div>
                        <div class="candidate-stat-label">Mesas</div>
                    </div>
                </div>

                <div class="candidate-track-progress">
                    <div class="candidate-progress-bar">
                        <div class="candidate-progress-fill" style="width: ${progressWidth}%; background: ${candidateColor}"></div>
                    </div>
                    <div class="candidate-progress-labels">
                        <span>0</span>
                        <span>${formatNumber(maxVotes)}</span>
                    </div>
                </div>

                <div class="candidate-trend ${candidate.trend}">
                    <span>${trendIcon}</span>
                    <span>${trendText}</span>
                </div>
            </div>
        `;
    }).join('');
}

async function loadCandidatesFromAPI() {
    try {
        const response = await fetch('/api/campaign-team/reports/votes-by-candidate?contest_id=1');
        const data = await response.json();

        if (data.success && data.candidates) {
            if (trackedCandidates.length === 0) {
                trackedCandidates = data.candidates.map((apiCandidate, index) => ({
                    id: apiCandidate.id || index + 1,
                    name: apiCandidate.name,
                    party: apiCandidate.party || apiCandidate.list || 'N/A',
                    color: apiCandidate.color || getPartyColor(index),
                    votes: apiCandidate.votes || 0,
                    percentage: apiCandidate.percentage || 0,
                    mesas: apiCandidate.mesas_processed || 0,
                    position: null,
                    trend: apiCandidate.trend || 'stable',
                    trendValue: apiCandidate.trend_value || 0
                }));
            }
            // Update trackedCandidates with API data
            data.candidates.forEach(apiCandidate => {
                const candidate = trackedCandidates.find(c => c.name === apiCandidate.name);
                if (candidate) {
                    candidate.votes = apiCandidate.votes || 0;
                    candidate.percentage = apiCandidate.percentage || 0;
                    candidate.mesas = apiCandidate.mesas_processed || 0;
                    candidate.trend = apiCandidate.trend || 'stable';
                    candidate.trendValue = apiCandidate.trend_value || 0;
                    candidate.color = apiCandidate.color || candidate.color;
                    candidate.coverage = apiCandidate.coverage_pct || 0;
                }
            });
        }
    } catch (error) {
        console.error('Error loading candidates from API:', error);
    }
}

function simulateCandidateDataFallback() {
    // Fallback data disabled to avoid mock values
    trackedCandidates.forEach(candidate => {
        candidate.votes = 0;
        candidate.percentage = 0;
        candidate.mesas = 0;
        candidate.trend = 'stable';
        candidate.trendValue = 0;
    });
}

function updateTrackedCandidatesFromE14(e14Candidates) {
    // Match E-14 candidates with tracked candidates
    if (!e14Candidates) return;

    // In a real implementation, we would match by candidate name/number
    // For now, just trigger a re-render
    renderTrackedCandidates();
}

// ============================================================
// E-14 LIVE FORM RENDERING
// ============================================================

let currentE14Data = null;
let previousCandidates = {};

function renderE14LiveForm(data) {
    const container = document.getElementById('e14-form-container');
    if (!container) return;

    // Check if we have Tesseract/Congress data
    const source = data.source || 'unknown';
    const partySummary = data.party_summary || [];
    const forms = data.forms || [];
    const totalForms = data.total_forms || forms.length || 0;
    const stats = data.stats || {};
    const totalVotes = stats.total_votes || data.total_votes || 0;
    const totalBlancos = stats.votos_blancos ?? data.votos_blancos ?? 0;
    const totalNulos = stats.votos_nulos ?? data.votos_nulos ?? 0;
    const totalUrna = totalVotes + totalBlancos + totalNulos;
    const totalParties = data.total_parties || partySummary.length || 0;

    // Determine election type from data
    const isCongressData = source === 'tesseract' || partySummary.length > 0;
    const firstForm = forms[0] || {};
    const header = firstForm.header || {};

    // Update header - show election name based on source
    const formsCountEl = document.getElementById('e14-forms-count');
    if (formsCountEl) formsCountEl.textContent = formatNumber(totalForms);

    const electionNameEl = document.getElementById('e14-election-name');
    if (electionNameEl) {
        if (isCongressData) {
            electionNameEl.textContent = header.election_name || 'CONGRESO 2022';
        } else {
            electionNameEl.textContent = header.election_name || 'E-14';
        }
    }

    // Calculate average confidence from party_summary or forms
    let avgConfidence = 0;
    if (partySummary.length > 0) {
        const confSum = partySummary.reduce((sum, p) => sum + (p.avg_confidence || 0), 0);
        avgConfidence = (confSum / partySummary.length) * 100;
    } else if (forms.length > 0) {
        const confSum = forms.reduce((sum, f) => sum + (f.overall_confidence || 0), 0);
        avgConfidence = (confSum / forms.length) * 100;
    }

    // Update confidence with color class
    const confidenceEl = document.getElementById('e14-confidence');
    if (confidenceEl) {
        confidenceEl.textContent = `${avgConfidence.toFixed(0)}%`;
        confidenceEl.className = 'e14-meta-value e14-confidence';
        confidenceEl.classList.add(confidenceClass(avgConfidence));
    }

    // Update location bar with data from first form or aggregated stats
    document.getElementById('e14-dept').textContent = header.departamento || '--';
    document.getElementById('e14-muni').textContent = header.municipio || '--';
    document.getElementById('e14-puesto').textContent = header.puesto || '--';
    document.getElementById('e14-mesa').textContent = totalForms ? formatNumber(totalForms) : '--';
    document.getElementById('e14-zona').textContent = header.zona || '--';

    const dateEl = document.getElementById('e14-date');
    if (dateEl) {
        dateEl.textContent = header.election_date || '--';
    }

    // Update nivelación with totals
    const totalSufragantes = totalUrna;
    document.getElementById('e14-sufragantes').textContent = formatNumber(totalSufragantes);
    document.getElementById('e14-urna').textContent = formatNumber(totalUrna);
    document.getElementById('e14-validos').textContent = formatNumber(totalVotes);
    document.getElementById('e14-blancos').textContent = formatNumber(totalBlancos);
    document.getElementById('e14-nulos').textContent = formatNumber(totalNulos);

    // Render candidates/parties based on data source
    if (isCongressData && partySummary.length > 0) {
        // Render Congress 2022 parties from Tesseract data
        const topParties = partySummary.slice(0, 15).map((p, index) => ({
            candidate_name: p.party_name,
            party_name: `${p.mesas_count} mesas`,
            votes: p.total_votes,
            confidence: p.avg_confidence || 0.85,
            color: getPartyColor(index),
            is_party_vote: true
        }));
        renderPresidentialCandidates(topParties);
    } else {
        const trackedCands = data.tracked_candidates || [];
        if (trackedCands.length > 0) {
            renderPresidentialCandidates(trackedCands);
        } else {
            renderPresidentialCandidates([]);
        }
    }

    // Update footer with appropriate info
    const coveragePercent = totalForms > 0 ? Math.round((totalForms / 500) * 100) : 0;
    document.getElementById('e14-extraction-info').textContent =
        `Actualizado: ${new Date().toLocaleString('es-CO')} | ${isCongressData ? `${totalParties} partidos | ${formatNumber(totalVotes)} votos` : `Cobertura: ${coveragePercent}%`}`;

    // Update E-14 timestamp
    const e14TimeEl = document.getElementById('e14-update-time');
    if (e14TimeEl) {
        e14TimeEl.textContent = new Date().toLocaleTimeString('es-CO', { hour: '2-digit', minute: '2-digit' });
    }
}

// Helper function to get party colors for Congress parties
function getPartyColor(index) {
    const colors = [
        '#E91E63', '#D32F2F', '#1565C0', '#388E3C', '#43A047',
        '#FF9800', '#7B1FA2', '#00ACC1', '#5E35B1', '#F44336',
        '#2196F3', '#4CAF50', '#FFC107', '#9C27B0', '#00BCD4'
    ];
    return colors[index % colors.length];
}

function renderPresidentialCandidates(candidates) {
    const grid = document.getElementById('e14-candidates-grid');
    if (!grid) return;

    if (!candidates || candidates.length === 0) {
        grid.innerHTML = '<div class="e14-empty">No hay candidatos registrados</div>';
        return;
    }

    // Sort by votes descending
    const sorted = [...candidates].sort((a, b) => (b.votes || 0) - (a.votes || 0));

    grid.innerHTML = sorted.map((candidate, index) => {
        const confidence = (candidate.confidence || 0.87) * 100;
        const confClass = confidenceClass(confidence);
        const color = candidate.color || '#C9A227';
        const position = index + 1;
        const positionClass = position <= 3 ? 'top-position' : '';

        return `
            <div class="e14-candidate-row ${positionClass}" style="border-left: 3px solid ${color}">
                <div class="e14-candidate-info">
                    <span class="e14-candidate-position">#${position}</span>
                    <span class="e14-candidate-name"><strong>${candidate.name || candidate.candidate_name}</strong></span>
                    <span class="e14-candidate-party" style="color: ${color}">${candidate.party || candidate.party_name}</span>
                </div>
                <div class="e14-candidate-votes">${formatNumber(candidate.votes || 0)}</div>
                <div class="e14-candidate-ocr">
                    <div class="e14-ocr-bar">
                        <div class="e14-ocr-fill ${confClass}" style="width: ${confidence}%; background: ${color}"></div>
                    </div>
                    <span class="e14-ocr-value">${confidence.toFixed(0)}%</span>
                </div>
            </div>
        `;
    }).join('');
}

function renderE14Candidates(candidates) {
    const grid = document.getElementById('e14-candidates-grid');
    if (!grid) return;

    if (!candidates || candidates.length === 0) {
        grid.innerHTML = '<div class="e14-empty">No hay candidatos registrados</div>';
        return;
    }

    grid.innerHTML = candidates.map((candidate, index) => {
        const confidence = (candidate.confidence || 0.85) * 100;
        const confClass = confidenceClass(confidence);
        const needsReview = candidate.needs_review ? 'needs-review' : '';

        // Check if this candidate was updated (vote count changed)
        const prevVotes = previousCandidates[candidate.candidate_number];
        const wasUpdated = prevVotes !== undefined && prevVotes !== candidate.votes;
        const updatedClass = wasUpdated ? 'updated' : '';

        // Store current votes for next comparison
        previousCandidates[candidate.candidate_number] = candidate.votes;

        const displayName = candidate.is_party_vote
            ? `<strong>${truncateText(candidate.party_name, 40)}</strong> (Lista)`
            : `#${candidate.candidate_number}`;

        return `
            <div class="e14-candidate-row ${needsReview} ${updatedClass}">
                <div class="e14-candidate-info">
                    <span class="e14-candidate-name">${displayName}</span>
                    ${!candidate.is_party_vote ? `<span class="e14-candidate-party">${truncateText(candidate.party_name, 35)}</span>` : ''}
                </div>
                <div class="e14-candidate-votes">${formatNumber(candidate.votes)}</div>
                <div class="e14-candidate-ocr">
                    <div class="e14-ocr-bar">
                        <div class="e14-ocr-fill ${confClass}" style="width: ${confidence}%"></div>
                    </div>
                    <span class="e14-ocr-value">${confidence.toFixed(0)}%</span>
                </div>
            </div>
        `;
    }).join('');
}

function renderE14Empty() {
    const grid = document.getElementById('e14-candidates-grid');
    if (grid) {
        grid.innerHTML = `
            <div class="e14-empty">
                <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" style="margin-bottom: 1rem; opacity: 0.5;">
                    <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>
                    <polyline points="14 2 14 8 20 8"/>
                    <line x1="16" y1="13" x2="8" y2="13"/>
                    <line x1="16" y1="17" x2="8" y2="17"/>
                </svg>
                <p>No hay extracciones E-14 disponibles</p>
                <p style="font-size: 0.8rem; margin-top: 0.5rem;">Procese un formulario E-14 para ver los datos aquí</p>
            </div>
        `;
    }

    // Clear header values
    const formsCountEl = document.getElementById('e14-forms-count');
    if (formsCountEl) formsCountEl.textContent = '0';
    document.getElementById('e14-election-name').textContent = 'Sin datos';
    document.getElementById('e14-mesa').textContent = '--';
    document.getElementById('e14-zona').textContent = '--';
    document.getElementById('e14-confidence').textContent = '--%';
}

async function refreshE14Data() {
    const container = document.getElementById('e14-form-container');
    const hasE14UI = !!container;
    if (container) container.classList.add('updating');

    try {
        const response = await fetch('/api/campaign-team/e14-live?limit=500');
        const data = await response.json();

        if (data.success) {
            // Store data globally for other functions
            window.e14LiveData = data;

            // Render the E-14 form if UI exists
            if (hasE14UI) {
                renderE14LiveForm(data);
            }

            // Process votes data for the votes table
            if (typeof processE14VotesData === 'function') {
                processE14VotesData();
            }

        }
    } catch (error) {
        console.error('Error refreshing E-14 data:', error);
    } finally {
        if (container) setTimeout(() => container.classList.remove('updating'), 500);
    }
}

// Make refresh function global
window.refreshE14Data = refreshE14Data;

// Webhook-first mode: E-14 updates arrive via backend webhook + manual refresh.

// ============================================================
// E-14 FILTER FUNCTIONALITY
// ============================================================

let e14Filters = {
    dept: '',
    muni: '',
    puesto: '',
    mesa: '',
    risk: ''
};

// Load filter options from data
async function loadE14FilterOptions() {
    try {
        // Get departments from geography endpoint
        const deptResponse = await fetch('/api/geography/choropleth?mode=coverage');
        const deptData = await deptResponse.json();

        const deptSelect = document.getElementById('e14-filter-dept');
        if (!deptSelect) return;
        if (deptSelect && deptData.features) {
            // Clear existing options
            deptSelect.innerHTML = '<option value="">Todos</option>';

            // Sort departments by name
            const depts = deptData.features
                .map(f => ({ code: f.properties.code, name: f.properties.name }))
                .sort((a, b) => a.name.localeCompare(b.name));

            depts.forEach(dept => {
                const option = document.createElement('option');
                option.value = dept.code;
                option.textContent = dept.name;
                deptSelect.appendChild(option);
            });
        }
    } catch (error) {
        console.error('Error loading E-14 filter options:', error);
    }
}

function filterE14ByDept() {
    const deptSelect = document.getElementById('e14-filter-dept');
    e14Filters.dept = deptSelect.value;

    // Reset dependent filters
    document.getElementById('e14-filter-muni').innerHTML = '<option value="">Todos</option>';
    document.getElementById('e14-filter-puesto').innerHTML = '<option value="">Todos</option>';
    document.getElementById('e14-filter-mesa').innerHTML = '<option value="">Todas</option>';
    e14Filters.muni = '';
    e14Filters.puesto = '';
    e14Filters.mesa = '';

    if (e14Filters.dept) {
        loadMunicipiosForDept(e14Filters.dept);
    }

    applyE14Filters();
}

async function loadMunicipiosForDept(deptCode) {
    // For now, populate with demo municipalities
    const muniSelect = document.getElementById('e14-filter-muni');
    muniSelect.innerHTML = '<option value="">Todos</option>';

    // Demo municipalities - in production this would come from an API
    for (let i = 1; i <= 10; i++) {
        const option = document.createElement('option');
        option.value = `${deptCode}-${String(i).padStart(3, '0')}`;
        option.textContent = `Municipio ${i}`;
        muniSelect.appendChild(option);
    }
}

function filterE14ByMuni() {
    const muniSelect = document.getElementById('e14-filter-muni');
    e14Filters.muni = muniSelect.value;

    // Reset dependent filters
    document.getElementById('e14-filter-puesto').innerHTML = '<option value="">Todos</option>';
    document.getElementById('e14-filter-mesa').innerHTML = '<option value="">Todas</option>';
    e14Filters.puesto = '';
    e14Filters.mesa = '';

    if (e14Filters.muni) {
        loadPuestosForMuni(e14Filters.muni);
    }

    applyE14Filters();
}

async function loadPuestosForMuni(muniCode) {
    const puestoSelect = document.getElementById('e14-filter-puesto');
    puestoSelect.innerHTML = '<option value="">Todos</option>';

    // Demo puestos
    for (let i = 1; i <= 5; i++) {
        const option = document.createElement('option');
        option.value = `${muniCode}-${String(i).padStart(2, '0')}`;
        option.textContent = `Puesto ${i}`;
        puestoSelect.appendChild(option);
    }
}

function filterE14ByPuesto() {
    const puestoSelect = document.getElementById('e14-filter-puesto');
    e14Filters.puesto = puestoSelect.value;

    // Reset mesa filter
    document.getElementById('e14-filter-mesa').innerHTML = '<option value="">Todas</option>';
    e14Filters.mesa = '';

    if (e14Filters.puesto) {
        loadMesasForPuesto(e14Filters.puesto);
    }

    applyE14Filters();
}

async function loadMesasForPuesto(puestoCode) {
    const mesaSelect = document.getElementById('e14-filter-mesa');
    mesaSelect.innerHTML = '<option value="">Todas</option>';

    // Demo mesas
    for (let i = 1; i <= 8; i++) {
        const option = document.createElement('option');
        option.value = `${puestoCode}-${String(i).padStart(3, '0')}`;
        option.textContent = `Mesa ${i}`;
        mesaSelect.appendChild(option);
    }
}

function filterE14ByMesa() {
    const mesaSelect = document.getElementById('e14-filter-mesa');
    e14Filters.mesa = mesaSelect.value;
    applyE14Filters();
}

function filterE14ByRisk() {
    const riskSelect = document.getElementById('e14-filter-risk');
    e14Filters.risk = riskSelect.value;
    applyE14Filters();
}

async function applyE14Filters() {
    // Build query params
    const params = new URLSearchParams();
    params.append('limit', '500');  // Always get all forms
    if (e14Filters.dept) params.append('dept', e14Filters.dept);
    if (e14Filters.muni) params.append('muni', e14Filters.muni);
    if (e14Filters.puesto) params.append('puesto', e14Filters.puesto);
    if (e14Filters.mesa) params.append('mesa', e14Filters.mesa);
    if (e14Filters.risk) params.append('risk', e14Filters.risk);

    try {
        const url = `/api/campaign-team/e14-live?${params.toString()}`;
        const response = await fetch(url);
        const data = await response.json();

        if (data.success) {
            renderE14LiveForm(data);
        }
    } catch (error) {
        console.error('Error applying E-14 filters:', error);
    }
}

function clearE14Filters() {
    e14Filters = { dept: '', muni: '', puesto: '', mesa: '', risk: '' };

    const deptEl = document.getElementById('e14-filter-dept');
    const muniEl = document.getElementById('e14-filter-muni');
    const puestoEl = document.getElementById('e14-filter-puesto');
    const mesaEl = document.getElementById('e14-filter-mesa');
    const riskEl = document.getElementById('e14-filter-risk');

    if (deptEl) deptEl.value = '';
    if (muniEl) muniEl.innerHTML = '<option value="">Todos</option>';
    if (puestoEl) puestoEl.innerHTML = '<option value="">Todos</option>';
    if (mesaEl) mesaEl.innerHTML = '<option value="">Todas</option>';
    if (riskEl) riskEl.value = '';

    refreshE14Data();
}

// Make filter functions global
window.filterE14ByDept = filterE14ByDept;
window.filterE14ByMuni = filterE14ByMuni;
window.filterE14ByPuesto = filterE14ByPuesto;
window.filterE14ByMesa = filterE14ByMesa;
window.filterE14ByRisk = filterE14ByRisk;
window.clearE14Filters = clearE14Filters;

// Load filter options on page load
document.addEventListener('DOMContentLoaded', () => {
    if (document.getElementById('e14-filter-dept')) {
        loadE14FilterOptions();
    }
});

// ============================================================
// INCIDENT QUEUE FUNCTIONALITY
// ============================================================

let allIncidents = [];
let incidentFilter = 'all';
let incidentDateFilter = null; // kept for backward compat
let incidentFilterRiesgo    = '';  // 'alto'|'medio'|'bajo'|''
let incidentFilterDept      = '';  // department name
let incidentFilterCorp      = '';  // 'SEN'|'CAM'|''
let incidentFilterHoraDesde = '';  // 'HH:MM'
let incidentFilterHoraHasta = '';  // 'HH:MM'
let incidentFilterId        = '';  // numeric ID substring
let incidentSortField = 'processed_at';
let incidentSortDir   = 'desc';
let incidentPage = 0;
const INCIDENT_PAGE_SIZE = 100;
let selectedIncidentId = null;
let timelineCountdown = 30;

// Initialize incident queue on page load
document.addEventListener('DOMContentLoaded', () => {
    setupIncidentFilters();
    loadIncidents();
    loadWarRoomKPIs();
    startTimelineCountdown();
});

function setupIncidentFilters() {
    document.querySelectorAll('.incident-filter-btn').forEach(btn => {
        btn.addEventListener('click', () => {
            // Update active state
            document.querySelectorAll('.incident-filter-btn').forEach(b => b.classList.remove('active'));
            btn.classList.add('active');

            // Update filter and re-render
            incidentFilter = btn.dataset.filter;
            incidentPage = 0;
            renderIncidentTable();
        });
    });
}

async function loadIncidents() {
    let resolvedData = null;
    try {
        // Load incidents from PMSN alerts (already fetched in loadDashboardData)
        const pmsnData = window.e14Data?.pmsnAlerts;
        if (!pmsnData || !pmsnData.alerts || pmsnData.alerts.length === 0) {
            // Fallback: fetch directly if not yet loaded
            const response = await fetch('/api/e14-data/pmsn-alerts');
            const data = await response.json();
            if (window.e14Data) window.e14Data.pmsnAlerts = data;
            resolvedData = data;
        } else {
            resolvedData = pmsnData;
        }
        loadIncidentsFromPMSN(resolvedData);
    } catch (error) {
        console.error('Error loading PMSN incidents:', error);
        const tbody = document.getElementById('incident-tbody');
        if (tbody) {
            tbody.innerHTML = '<tr><td colspan="13" style="text-align: center; color: var(--muted);">Error cargando incidentes PMSN</td></tr>';
        }
    }
    // renderPMSNUmbralMesas runs independently so its errors never corrupt the incident table
    if (resolvedData) {
        try { renderPMSNUmbralMesas(resolvedData); } catch (e) {
            console.error('Error rendering PMSN umbral mesas:', e);
        }
    }
}

function loadIncidentsFromPMSN(pmsnData) {
    const alerts = pmsnData.alerts || [];
    const severityMap = { 'R_ALTO': 'P0', 'R_MEDIO': 'P1', 'R_BAJO': 'P2' };
    const riskOrder  = { 'R_ALTO': 3, 'R_MEDIO': 2, 'R_BAJO': 1 };

    // Group alerts by physical mesa coordinates (dept+muni+mesa_num) when available,
    // falling back to form_id. This deduplicates the same physical acta processed
    // multiple times (producing distinct form_ids) — defense-in-depth vs store dedup.
    const byMesa = new Map();
    alerts.forEach((alert, idx) => {
        const corp = (alert.corporacion || '').toUpperCase().includes('SENAD') ? 'SEN' : 'CAM';
        // physKey uses corp+dept+muni+zona+mesa_num (NOT puesto_cod) so that OCR
        // misreads of puesto (e.g. '00' vs 'CABECERA MUNICIPAL') don't create
        // duplicate incident rows for the same physical mesa.
        // Strip leading "- " OCR artifacts from dept/muni before keying.
        const normDept = (alert.departamento || '').replace(/^[-\s]+/, '').trim().toUpperCase();
        const normMuni = (alert.municipio    || '').replace(/^[-\s]+/, '').trim().toUpperCase();
        const physKey = (normDept && normMuni && alert.mesa_num)
            ? `${corp}|${normDept}|${normMuni}|${alert.zona_cod||''}|${alert.mesa_num}`
            : null;
        const key = physKey || (alert.form_id != null ? `form_${alert.form_id}` : (alert.mesa_id || `__nomesa_${idx}`));
        if (!byMesa.has(key)) {
            byMesa.set(key, {
                id: byMesa.size,
                form_id: alert.form_id,
                mesa_id: alert.mesa_id || '',
                dept_name: alert.departamento || '',
                muni_name: alert.municipio || '',
                zona: alert.zona_cod || '',
                puesto: alert.puesto_cod || '',
                puesto_name: alert.puesto_nombre || alert.lugar || '',
                lugar: alert.lugar || '',
                mesa: alert.mesa_num || '',
                corporacion: alert.corporacion || '',
                comision: alert.corporacion || '',
                processed_at: alert.processed_at || null,
                ocr_confidence: null,
                status: 'OPEN',
                total_votes: alert.total_votos ?? 0,
                votos_afectados: 0,
                pmsn_votes: alert.pmsn_votes ?? 0,
                // aggregated fields (updated to highest-risk below)
                severity: 'P2',
                risk_type: 'R_BAJO',
                rule_id: '',
                description: '',
                risk_label: '',
                incident_type: '',
                rules: [],
            });
        }
        const inc = byMesa.get(key);
        // Dedup rules by rule_id (same rule can appear from multiple processed copies of the same mesa)
        if (!inc.rules.some(r => r.rule_id === alert.rule_id)) {
            inc.rules.push({
                rule_id: alert.rule_id,
                risk_type: alert.risk_type,
                risk_label: alert.risk_label || '',
                description: alert.description || '',
                details: alert.details || {},
            });
        }
        // Promote to highest-risk rule
        if ((riskOrder[alert.risk_type] || 0) > (riskOrder[inc.risk_type] || 0)) {
            inc.risk_type    = alert.risk_type;
            inc.severity     = severityMap[alert.risk_type] || 'P2';
            inc.rule_id      = alert.rule_id;
            inc.description  = alert.description || '';
            inc.risk_label   = alert.risk_label || '';
            inc.incident_type = alert.rule_id;
        }
        // Keep most-recent processed_at across deduplicated copies of the same mesa
        if (alert.processed_at && (!inc.processed_at || alert.processed_at > inc.processed_at)) {
            inc.processed_at = alert.processed_at;
        }
        // Keep non-zero total_votes (first form with a real count wins)
        if ((alert.total_votos ?? 0) > 0 && inc.total_votes === 0) {
            inc.total_votes = alert.total_votos;
        }
    });

    allIncidents = Array.from(byMesa.values());
    populateIncidentDeptFilter();

    updateIncidentStats({
        p0_count: allIncidents.filter(i => i.severity === 'P0').length,
        p1_count: allIncidents.filter(i => i.severity === 'P1').length,
        open_count: allIncidents.length,
    });
    renderIncidentTable();
    window.contiendaIncidencias = allIncidents;
    if (typeof updateContiendaStats === 'function') {
        updateContiendaStats();
    }
    window.dispatchEvent(new Event('contienda:incidents-updated'));
}

async function loadWarRoomKPIs() {
    try {
        const response = await fetch('/api/incidents/war-room/kpis');
        const data = await response.json();

        if (data.success) {
            updateWarRoomKPIs(data.kpis);
            updateTimeline(data.timeline, data.kpis);
        }
    } catch (error) {
        console.error('Error loading War Room KPIs:', error);
    }
}

function updateWarRoomKPIs(kpis) {
    const setEl = (id, val) => {
        const el = document.getElementById(id);
        if (el) el.textContent = val;
    };
    setEl('kpi-total', formatNumber(kpis.mesas_total));
    setEl('kpi-testigo', formatNumber(kpis.mesas_testigo));
    setEl('kpi-rnec', formatNumber(kpis.mesas_rnec));
    setEl('kpi-reconciled', formatNumber(kpis.mesas_reconciliadas));
    setEl('kpi-p0', kpis.incidentes_p0);
    setEl('kpi-coverage', `${kpis.cobertura_pct}%`);
}

function updateTimeline(timeline, kpis) {
    const setBar = (id, pct) => {
        const el = document.getElementById(id);
        if (el) el.style.width = `${pct}%`;
    };
    const setEl = (id, val) => {
        const el = document.getElementById(id);
        if (el) el.textContent = val;
    };

    // Update progress bars
    setBar('timeline-testigo-bar', kpis.testigo_pct);
    setEl('timeline-testigo-pct', `${kpis.testigo_pct}%`);

    setBar('timeline-rnec-bar', kpis.rnec_pct);
    setEl('timeline-rnec-pct', `${kpis.rnec_pct}%`);

    setBar('timeline-reconciled-bar', kpis.reconciliadas_pct);
    setEl('timeline-reconciled-pct', `${kpis.reconciliadas_pct}%`);

    // Update last RNEC update time
    if (kpis.last_rnec_update) {
        const lastUpdate = new Date(kpis.last_rnec_update);
        setEl('timeline-last-rnec', lastUpdate.toLocaleTimeString('es-CO', { hour: '2-digit', minute: '2-digit' }));
    }
}

function startTimelineCountdown() {
    const countdownEl = document.getElementById('timeline-countdown');
    if (!countdownEl) return; // Don't run if element doesn't exist

    countdownEl.textContent = 'manual';
}

function updateIncidentStats(data) {
    const setEl = (id, val) => {
        const el = document.getElementById(id);
        if (el) el.textContent = val;
    };
    setEl('incident-p0-count', data.p0_count || 0);
    setEl('incident-p1-count', data.p1_count || 0);
    setEl('incident-total-count', data.open_count || 0);
}

function sortIncidentTable(field) {
    if (field === incidentSortField) {
        incidentSortDir = incidentSortDir === 'asc' ? 'desc' : 'asc';
    } else {
        incidentSortField = field;
        incidentSortDir = (field === 'pmsn_votes' || field === 'processed_at') ? 'desc' : 'asc';
    }
    incidentPage = 0;
    const sortFields = ['dept_name', 'muni_name', 'zona', 'puesto', 'mesa', 'total_votes', 'pmsn_votes', 'riskActa', 'processed_at'];
    sortFields.forEach(f => {
        const el = document.getElementById(`sort-icon-${f}`);
        if (el) el.textContent = f === incidentSortField ? (incidentSortDir === 'asc' ? '▲' : '▼') : '';
    });
    renderIncidentTable();
}

function renderIncidentTable() {
    const tbody = document.getElementById('incident-tbody');
    if (!tbody) return;

    // Ensure ID filter input exists in the filter bar — inject once if missing
    if (!document.getElementById('incident-filter-id')) {
        const limpiarBtn = document.querySelector('button[onclick="clearIncidentFilters()"]');
        if (limpiarBtn) {
            const idInput = document.createElement('input');
            idInput.type = 'text';
            idInput.id = 'incident-filter-id';
            idInput.placeholder = 'Buscar ID...';
            idInput.title = 'Filtrar por ID de caso';
            idInput.style.cssText = 'border:1px solid var(--border);border-radius:4px;padding:0.22rem 0.5rem;font-size:0.75rem;background:var(--card-bg,#fff);color:var(--text);width:90px;';
            idInput.oninput = () => applyIncidentFilters();
            limpiarBtn.insertAdjacentElement('beforebegin', idInput);
        }
    }

    // Filter incidents
    let filtered = [...allIncidents];
    if (incidentFilter !== 'all') {
        if (['P0', 'P1', 'P2', 'P3'].includes(incidentFilter)) {
            filtered = filtered.filter(i => i.severity === incidentFilter);
        } else if (['OPEN', 'ASSIGNED', 'INVESTIGATING'].includes(incidentFilter)) {
            filtered = filtered.filter(i => i.status === incidentFilter);
        }
    }
    if (incidentFilterRiesgo) {
        filtered = filtered.filter(i => getRiskActaLevel(i) === incidentFilterRiesgo);
    }
    if (incidentFilterDept) {
        filtered = filtered.filter(i =>
            resolveDeptName(i).toUpperCase() === incidentFilterDept.toUpperCase());
    }
    if (incidentFilterCorp) {
        const _corpTarget = incidentFilterCorp === 'SEN' ? 'SENADO' : 'CAMARA';
        filtered = filtered.filter(i =>
            (i.corporacion || '').toUpperCase() === _corpTarget);
    }
    if (incidentFilterHoraDesde || incidentFilterHoraHasta) {
        filtered = filtered.filter(i => {
            if (!i.processed_at) return false;
            const _dt2 = new Date(i.processed_at);
            const _hhmm = `${String(_dt2.getHours()).padStart(2,'0')}:${String(_dt2.getMinutes()).padStart(2,'0')}`;
            if (incidentFilterHoraDesde && _hhmm < incidentFilterHoraDesde) return false;
            if (incidentFilterHoraHasta && _hhmm > incidentFilterHoraHasta) return false;
            return true;
        });
    }

    if (incidentFilterId) {
        filtered = filtered.filter(i => String(i.id).includes(incidentFilterId));
    }

    if (filtered.length === 0) {
        tbody.innerHTML = '<tr><td colspan="15" style="text-align: center; color: var(--muted);">No hay incidentes con este filtro</td></tr>';
        return;
    }

    const riskColors = { 'R_ALTO': '#E05252', 'R_MEDIO': '#F07030', 'R_BAJO': '#D4A017' };
    const riskOrder = { 'p0': 0, 'p1': 1, 'p2': 2, 'p3': 3 };

    const sorted = [...filtered].sort((a, b) => {
        if (incidentSortField === 'pmsn_votes') {
            const diff = (a.pmsn_votes || 0) - (b.pmsn_votes || 0);
            return incidentSortDir === 'asc' ? diff : -diff;
        }
        if (incidentSortField === 'total_votes') {
            const diff = (a.total_votes || 0) - (b.total_votes || 0);
            return incidentSortDir === 'asc' ? diff : -diff;
        }
        if (incidentSortField === 'riskActa') {
            const ra = riskOrder[(getRiskActaLevel(a) || 'p3').toLowerCase()] ?? 3;
            const rb = riskOrder[(getRiskActaLevel(b) || 'p3').toLowerCase()] ?? 3;
            return incidentSortDir === 'asc' ? ra - rb : rb - ra;
        }
        if (incidentSortField === 'processed_at') {
            const ta = a.processed_at ? new Date(a.processed_at).getTime() : 0;
            const tb = b.processed_at ? new Date(b.processed_at).getTime() : 0;
            return incidentSortDir === 'asc' ? ta - tb : tb - ta;
        }
        const va = (a[incidentSortField] || '').toString().toLowerCase();
        const vb = (b[incidentSortField] || '').toString().toLowerCase();
        return incidentSortDir === 'asc' ? va.localeCompare(vb) : vb.localeCompare(va);
    });
    // Pagination slice
    const totalPages = Math.ceil(sorted.length / INCIDENT_PAGE_SIZE);
    if (incidentPage >= totalPages) incidentPage = Math.max(0, totalPages - 1);
    const pageStart = incidentPage * INCIDENT_PAGE_SIZE;
    const pageEnd   = Math.min(pageStart + INCIDENT_PAGE_SIZE, sorted.length);
    const pageItems = sorted.slice(pageStart, pageEnd);

    const seenMesas = getSeenMesas();
    tbody.innerHTML = pageItems.map(incident => {
        incident._tesseract_record = findTesseractRecordForIncident(incident);
        const riskActa = getRiskActaLevel(incident);
        const dept  = resolveDeptName(incident);
        const muni  = resolveMuniName(incident);
        const zona  = resolveZona(incident);
        const puesto = resolvePuestoName(incident);
        const mesa  = resolveMesaLabel(incident);
        const isNew = !seenMesas.has(String(incident.mesa_id));
        const newBadge = isNew
            ? `<span class="badge-nueva" data-mesa="${incident.mesa_id}" title="Acta nueva — pendiente de revisión">NUEVO</span>`
            : '';

        // Build one pill per PMSN rule
        const rules = incident.rules && incident.rules.length ? incident.rules : [{
            rule_id: incident.rule_id || incident.incident_type || '—',
            risk_type: incident.risk_type,
            description: incident.description || 'Anomalía',
        }];
        const alertsHtml = rules.map(r => {
            const c = riskColors[r.risk_type] || '#777';
            return `<div style="display:flex;align-items:flex-start;gap:0.35rem;margin-bottom:3px;">
                <span style="font-size:0.68rem;font-weight:700;color:${c};min-width:58px;flex-shrink:0;padding-top:1px;">${escapeHtml(r.rule_id)}</span>
                <span style="font-size:0.75rem;color:var(--text-secondary);line-height:1.3;">${escapeHtml(r.description)}</span>
            </div>`;
        }).join('');

        const _dt = incident.processed_at ? new Date(incident.processed_at) : null;
        const _fecha = _dt ? `${String(_dt.getDate()).padStart(2,'0')}/${String(_dt.getMonth()+1).padStart(2,'0')}/${_dt.getFullYear()}` : '—';
        const _hora  = _dt ? `${String(_dt.getHours()).padStart(2,'0')}:${String(_dt.getMinutes()).padStart(2,'0')}` : '—';
        const _corp = (incident.corporacion || '').toUpperCase();
        const _corpLabel = _corp === 'SENADO' ? 'SEN' : _corp === 'CAMARA' ? 'CAM' : (_corp.slice(0, 3) || '—');
        const _corpColor = _corp === 'SENADO' ? '#6366F1' : _corp === 'CAMARA' ? '#0EA5E9' : '#9CA3AF';
        const mesaIdRaw = String(incident.mesa_id || '');
        const mesaIdJs = mesaIdRaw.replace(/\\/g, '\\\\').replace(/'/g, "\\'");
        const incidentIdVal = Number.isFinite(Number(incident.id)) ? Number(incident.id) : 'null';
        const formIdVal = Number.isFinite(Number(incident.form_id)) ? Number(incident.form_id) : 'null';
        return `
            <tr onclick="openIncidentDetail(${incident.id})" style="cursor:pointer;" data-level="${riskActa}" data-type="${classifyIncidentCategory(incident)}">
                <td><input type="checkbox" class="incident-check" data-id="${incident.id}" onclick="event.stopPropagation();"></td>
                <td style="padding:0.3rem 0.5rem; font-size:0.72rem; font-weight:600; color:var(--muted); white-space:nowrap; font-family:monospace;">${newBadge}#${incident.id}</td>
                <td class="incident-mesa">${escapeHtml(dept)}</td>
                <td class="incident-mesa">${escapeHtml(muni)}</td>
                <td class="incident-mesa">${escapeHtml(zona)}</td>
                <td class="incident-mesa">${escapeHtml(puesto)}</td>
                <td class="incident-mesa">${escapeHtml(mesa)}</td>
                <td style="padding:0.3rem 0.5rem;"><span style="display:inline-block;padding:0.15rem 0.45rem;border-radius:4px;background:${_corpColor};color:#fff;font-size:0.7rem;font-weight:600;">${_corpLabel}</span></td>
                <td style="padding:0.3rem 0.5rem;font-size:0.75rem;white-space:nowrap;">${_fecha}</td>
                <td style="padding:0.3rem 0.5rem;font-size:0.75rem;white-space:nowrap;">${_hora}</td>
                <td style="text-align:right; padding:0.3rem 0.5rem; font-size:0.75rem;">${formatNumber(incident.total_votes || 0)}</td>
                <td style="text-align:right; padding:0.3rem 0.5rem; font-weight:600; color:#C9A84C;">${formatNumber(incident.pmsn_votes || 0)}</td>
                <td><span class="severity-badge ${riskActa}">${riskActa.toUpperCase()}</span></td>
                <td style="min-width:260px;padding:0.4rem 0.5rem;">${alertsHtml}</td>
                <td style="white-space:nowrap;">
                    <button class="incident-action-btn" onclick="event.stopPropagation();openMesaDetailFromIncident('${mesaIdJs}')" title="Revisar formulario E-14">
                        Revisar
                    </button>
                    <button class="incident-action-btn danger" onclick="event.stopPropagation();openImpugnarModal('${mesaIdJs}', ${incidentIdVal}, ${formIdVal})" title="Impugnar esta mesa" style="margin-left:0.3rem;">
                        Impugnar
                    </button>
                </td>
            </tr>
        `;
    }).join('');

    // Counter label: "100 / 340 mesas"
    const countLabel = `${pageItems.length} / ${sorted.length} mesas`;
    const headerCountEl = document.getElementById('incident-count-header');
    if (headerCountEl) headerCountEl.textContent = countLabel;

    // Render pagination controls (footer)
    const paginationEl = document.getElementById('incident-pagination');
    if (paginationEl) {
        const btnStyle = `padding:0.3rem 0.75rem; border:1px solid var(--border,#ddd); border-radius:6px; background:var(--card-bg,#fff); color:var(--text,#111); cursor:pointer; font-size:0.8rem;`;
        const disabledStyle = `padding:0.3rem 0.75rem; border:1px solid var(--border,#ddd); border-radius:6px; background:var(--card-bg,#f5f5f5); color:var(--muted,#aaa); cursor:default; font-size:0.8rem;`;
        if (totalPages <= 1) {
            paginationEl.innerHTML = `<div style="font-size:0.78rem; color:var(--muted,#666); padding:0.4rem 0.2rem; text-align:right;">${countLabel}</div>`;
        } else {
            paginationEl.innerHTML = `
                <div style="display:flex; align-items:center; justify-content:flex-end; gap:0.5rem; padding:0.6rem 0.5rem 0.2rem;">
                    <span style="font-size:0.8rem; color:var(--muted,#666);">${countLabel} &nbsp;·&nbsp; pág. ${incidentPage + 1} / ${totalPages}</span>
                    <button onclick="incidentGoToPage(${incidentPage - 1})" ${incidentPage === 0 ? 'disabled style="' + disabledStyle + '"' : 'style="' + btnStyle + '"'}>&#8592; Anterior</button>
                    <button onclick="incidentGoToPage(${incidentPage + 1})" ${incidentPage >= totalPages - 1 ? 'disabled style="' + disabledStyle + '"' : 'style="' + btnStyle + '"'}>Siguiente &#8594;</button>
                </div>`;
        }
    }
}

function incidentGoToPage(page) {
    incidentPage = page;
    renderIncidentTable();
    // Scroll table into view
    const el = document.getElementById('incident-table');
    if (el) el.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
}

function getSlaClass(minutes) {
    if (minutes === null || minutes === undefined) return 'ok';
    if (minutes <= 5) return 'urgent';
    if (minutes <= 10) return 'warning';
    return 'ok';
}

function formatSlaTime(minutes) {
    if (minutes === null || minutes === undefined) return '--';
    if (minutes <= 0) return 'VENCIDO';
    if (minutes < 60) return `${minutes}m`;
    return `${Math.floor(minutes / 60)}h ${minutes % 60}m`;
}

function formatIncidentType(type) {
    if (typeof PMSN_RULE_META !== 'undefined' && PMSN_RULE_META[type]) {
        return `${type}: ${PMSN_RULE_META[type].label}`;
    }
    const typeMap = {
        'OCR_LOW_CONF': 'Ilegibilidad del Acta',
        'ARITHMETIC_FAIL': 'Error Suma',
        'E11_VS_URNA': 'E11≠Urna',
        'RECOUNT_MARKED': 'Recuento',
        'SIGNATURE_MISSING': 'Sin Firma',
        'RNEC_DELAY': 'RNEC Delay',
        'DISCREPANCY_RNEC': 'Δ RNEC',
        'SOURCE_MISMATCH': 'T≠Oficial',
        'AN': 'Anomalía'
    };
    return typeMap[type] || type;
}

function extractCodeAndName(value) {
    if (!value) return { code: null, name: null };
    const raw = String(value).trim();
    const match = raw.match(/^(\d{1,3})\s*[-–]\s*(.+)$/);
    if (match) {
        return { code: match[1], name: match[2].trim() };
    }
    return { code: null, name: raw };
}

function stripAccents(value) {
    return String(value || '')
        .normalize('NFD')
        .replace(/[\u0300-\u036f]/g, '');
}

function normalizeLookupText(value) {
    if (!value) return '';
    const raw = stripAccents(String(value)).trim();
    return raw.replace(/\s+/g, ' ').toUpperCase();
}

function normalizeLookupKey(value) {
    return normalizeLookupText(value).replace(/\s+/g, '-');
}

function normalizeCodeValue(value, width) {
    if (value === null || value === undefined) return '';
    const digits = String(value).replace(/\D/g, '');
    if (digits) {
        return digits.padStart(width, '0');
    }
    return String(value).trim();
}

async function loadMunicipioCatalog() {
    if (muniCatalogLoaded) return;
    muniCatalogLoaded = true;
    try {
        const response = await fetch('/static/data/municipios_dane.json');
        if (!response.ok) return;
        const data = await response.json();
        if (data && typeof data === 'object') {
            if (data.municipalities) {
                MUNI_CATALOG = data.municipalities;
            } else {
                MUNI_CATALOG = data;
            }
            if (data.departments) {
                DEPT_CODE_TO_NAME_RNEC = data.departments;
            }
            if (data.puestos) {
                PUESTO_CATALOG = data.puestos;
            }
        }
    } catch (error) {
        console.warn('No se pudo cargar catálogo de municipios DANE:', error);
    }
}

async function loadTesseractLookup() {
    if (tesseractLookupLoaded) return;
    tesseractLookupLoaded = true;
    try {
        const response = await fetch('/static/data/tesseract_e14_lookup.json');
        if (!response.ok) return;
        const data = await response.json();
        if (data && typeof data === 'object') {
            TESSERACT_LOOKUP = data;
        }
    } catch (error) {
        console.warn('No se pudo cargar lookup Tesseract:', error);
    }
}

function titleCaseWords(value) {
    if (!value) return value;
    const raw = String(value);
    return raw
        .toLowerCase()
        .replace(/\b([a-záéíóúñ])/g, match => match.toUpperCase());
}

function normalizeLocationName(value) {
    if (!value) return value;
    const { name } = extractCodeAndName(value);
    if (!name) return value;
    const isAllUpper = name === name.toUpperCase();
    const isAllLower = name === name.toLowerCase();
    return (isAllUpper || isAllLower) ? titleCaseWords(name) : name;
}

function buildE14GeoLookup(e14Data) {
    const forms = e14Data?.forms || [];
    const deptByCode = {};
    const muniByCode = {};

    forms.forEach(form => {
        const header = form.header || {};
        const deptCodeRaw = header.departamento_code || header.dept_code || header.departamento_cod;
        const deptNameRaw = header.departamento_name || header.departamento || header.dept_name;
        const muniCodeRaw = header.municipio_code || header.muni_code || header.municipio_cod;
        const muniNameRaw = header.municipio_name || header.municipio || header.muni_name;

        const deptParsed = extractCodeAndName(deptNameRaw);
        const muniParsed = extractCodeAndName(muniNameRaw);

        const deptCode = deptCodeRaw || deptParsed.code;
        const deptName = normalizeLocationName(deptParsed.name || deptNameRaw);
        const muniCode = muniCodeRaw || muniParsed.code;
        const muniName = normalizeLocationName(muniParsed.name || muniNameRaw);

        if (deptCode && deptName) {
            deptByCode[String(deptCode).padStart(2, '0')] = deptName;
        }
        if (muniCode && muniName) {
            muniByCode[String(muniCode).padStart(3, '0')] = muniName;
        }
    });

    E14_GEO_LOOKUP = {
        deptByCode,
        muniByCode
    };
}

function parseMesaIdLocation(mesaId) {
    if (!mesaId) return {};
    const clusterMatch = /^CLUSTER-(\d+)/.exec(mesaId);
    if (clusterMatch) {
        return { mesa: clusterMatch[1] };
    }

    const parts = mesaId.split('-');
    if (parts.length >= 4) {
        const corp = parts[0].toUpperCase();
        if (['SENADO', 'CAMARA', 'PRESIDENCIA'].includes(corp)) {
            const dept = titleCaseWords(parts[1].replace(/_/g, ' '));
            const muni = titleCaseWords(parts[2].replace(/_/g, ' '));
            const mesa = parts.slice(3).join('-');
            return { dept, muni, mesa };
        }
    }
    const codedMatch = /^(\d{1,3})\s*[-–]\s*(.+)$/.exec(mesaId);
    if (codedMatch) {
        return { mesa: codedMatch[1] };
    }
    return {};
}

function getRawDeptName(incident) {
    if (incident.dept_name) return normalizeLocationName(incident.dept_name);
    if (incident.departamento) return normalizeLocationName(incident.departamento);
    if (incident.departamento_name) return normalizeLocationName(incident.departamento_name);
    if (incident.departamento_code) {
        const code = String(incident.departamento_code).padStart(2, '0');
        return DEPT_CODE_TO_NAME_RNEC[code] || DEPT_CODE_TO_NAME[code] || E14_GEO_LOOKUP.deptByCode[code] || incident.departamento_code;
    }
    if (incident.dept_code) {
        const code = String(incident.dept_code).toUpperCase();
        return DEPT_ABBR_TO_NAME[code] || DEPT_CODE_TO_NAME_RNEC[code] || DEPT_CODE_TO_NAME[code] || E14_GEO_LOOKUP.deptByCode[String(code).padStart(2, '0')] || incident.dept_code;
    }
    const parsed = parseMesaIdLocation(incident.mesa_id);
    if (parsed.dept) return parsed.dept;
    return null;
}

function getRawMuniName(incident) {
    if (incident.muni_name) return normalizeLocationName(incident.muni_name);
    if (incident.municipio) return normalizeLocationName(incident.municipio);
    if (incident.municipio_name) return normalizeLocationName(incident.municipio_name);
    if (incident.muni_code) {
        const code = String(incident.muni_code).padStart(3, '0');
        const deptCodeRaw = incident.dept_code || incident.departamento_code || incident.dept;
        const deptCode = deptCodeRaw ? String(deptCodeRaw).padStart(2, '0') : null;
        if (deptCode && MUNI_CATALOG[deptCode] && MUNI_CATALOG[deptCode][code]) {
            return MUNI_CATALOG[deptCode][code];
        }
        return E14_GEO_LOOKUP.muniByCode[code] || incident.muni_code;
    }
    const parsed = parseMesaIdLocation(incident.mesa_id);
    if (parsed.muni) return parsed.muni;
    return null;
}

function getRawZona(incident) {
    return incident.zona || incident.zona_cod || null;
}

function getRawMesa(incident) {
    if (incident.mesa_number) return incident.mesa_number;
    if (incident.mesa) return incident.mesa;
    const parsed = parseMesaIdLocation(incident.mesa_id);
    if (parsed.mesa) return parsed.mesa;
    return null;
}

function getRawPuesto(incident) {
    if (incident.puesto_name) return incident.puesto_name;
    if (incident.puesto) return incident.puesto;
    return null;
}

function findTesseractRecordForIncident(incident) {
    if (!TESSERACT_LOOKUP) return null;
    const byMesaId = TESSERACT_LOOKUP.by_mesa_id || {};
    const byLocation = TESSERACT_LOOKUP.by_location || {};
    const byMesa = TESSERACT_LOOKUP.by_mesa || {};

    const mesaId = incident.mesa_id || '';
    const directKey = normalizeLookupKey(mesaId);
    if (directKey && byMesaId[directKey]) return byMesaId[directKey];

    const deptName = getRawDeptName(incident);
    const muniName = getRawMuniName(incident);
    const zona = getRawZona(incident);
    const puesto = getRawPuesto(incident);
    const mesa = getRawMesa(incident);

    const deptKey = normalizeLookupText(deptName);
    const muniKey = normalizeLookupText(muniName);
    const zonaKey = normalizeCodeValue(zona, 2);
    const puestoKey = normalizeLookupText(puesto);
    const mesaKey = normalizeCodeValue(mesa, 3);

    if (deptKey && muniKey && mesaKey) {
        const mesaKeyCompact = `${deptKey}|${muniKey}|${mesaKey}`;
        if (byMesa[mesaKeyCompact] && byMesa[mesaKeyCompact].length > 0) {
            return byMesa[mesaKeyCompact][0];
        }
    }

    const locationKey = [deptKey, muniKey, zonaKey, puestoKey, mesaKey].join('|');
    if (locationKey && byLocation[locationKey]) return byLocation[locationKey];

    return null;
}

function resolveDeptName(incident) {
    const raw = getRawDeptName(incident);
    if (raw) return raw;
    const record = incident._tesseract_record;
    return (record && record.departamento) ? normalizeLocationName(record.departamento) : '--';
}

function resolveMuniName(incident) {
    const raw = getRawMuniName(incident);
    if (raw) return raw;
    const record = incident._tesseract_record;
    return (record && record.municipio) ? normalizeLocationName(record.municipio) : '--';
}

function resolveZona(incident) {
    const zona = incident.zona || incident.zona_cod;
    const record = incident._tesseract_record;
    const zonaVal = zona || (record && record.zona);
    if (!zonaVal) return '--';
    const zoneText = String(zonaVal);
    if (zoneText.toLowerCase().includes('zona')) return zoneText;
    return `Zona ${zoneText.padStart(2, '0')}`;
}

function resolveMesaLabel(incident) {
    const raw = getRawMesa(incident);
    if (raw) return raw;
    const record = incident._tesseract_record;
    return (record && record.mesa) ? record.mesa : (incident.mesa_id || '--');
}

function resolveDeptCode(incident) {
    if (incident.departamento_code) return String(incident.departamento_code).padStart(2, '0');
    if (incident.dept_code) {
        const code = String(incident.dept_code).toUpperCase();
        if (DEPT_ABBR_TO_CODE[code]) return DEPT_ABBR_TO_CODE[code];
        if (DEPT_CODE_TO_NAME_RNEC[code]) return String(code).padStart(2, '0');
    }
    return null;
}

function resolveMuniCode(incident) {
    if (incident.municipio_code) return String(incident.municipio_code).padStart(3, '0');
    if (incident.muni_code) return String(incident.muni_code).padStart(3, '0');
    return null;
}

function resolveZonaCode(incident) {
    const zona = incident.zona || incident.zona_cod;
    if (!zona) return null;
    return String(zona).padStart(2, '0');
}

function resolvePuestoName(incident) {
    if (incident.puesto_nombre) return normalizeLocationName(incident.puesto_nombre);
    if (incident.puesto_name) return normalizeLocationName(incident.puesto_name);
    if (incident.lugar) return normalizeLocationName(incident.lugar);
    const record = incident._tesseract_record;
    if (record && record.puesto) return normalizeLocationName(record.puesto);
    const deptCode = resolveDeptCode(incident);
    const muniCode = resolveMuniCode(incident);
    const zonaCode = resolveZonaCode(incident);
    const puestoCode = incident.puesto_cod || incident.puesto_code || incident.puesto_id || incident.puesto;
    if (deptCode && muniCode && zonaCode && puestoCode && PUESTO_CATALOG[deptCode]) {
        const zonaMap = PUESTO_CATALOG[deptCode]?.[muniCode]?.[zonaCode] || {};
        const key = String(puestoCode).padStart(2, '0');
        return zonaMap[key] || '--';
    }
    return '--';
}

function buildMesaLocation(incident) {
    const dept = incident.dept_name || incident.dept_code || '--';
    const muni = incident.muni_name || incident.muni_code || '--';
    const zona = incident.zona || incident.zona_cod || '--';
    const mesa = incident.mesa_id || '--';
    return `${dept} / ${muni} / Zona ${zona} / Mesa ${mesa}`;
}

function classifyIncidentCategory(incident) {
    return incident.rule_id || incident.incident_type || 'PMSN-00';
}

function getRiskDetectedLabel(incident) {
    const ruleId = incident.rule_id || incident.incident_type || '';
    const meta = typeof PMSN_RULE_META !== 'undefined' ? PMSN_RULE_META[ruleId] : null;
    if (meta) return `${ruleId}: ${meta.label}`;
    return ruleId || 'Anomalía';
}

function getRiskActaLevel(incident) {
    const riskType = (incident.risk_type || '').toUpperCase();
    if (riskType === 'R_ALTO') return 'alto';
    if (riskType === 'R_MEDIO') return 'medio';
    if (riskType === 'R_BAJO') return 'bajo';
    // Fallback by severity
    const severity = (incident.severity || '').toUpperCase();
    if (severity === 'P0') return 'alto';
    if (severity === 'P1') return 'medio';
    return 'bajo';
}

function formatPmsnDetails(details) {
    if (!details || typeof details !== 'object') return '';
    const labels = {
        diff: 'Diferencia', diff_pct: 'Diferencia %',
        computed_sum: 'Suma calculada', total_votos: 'Total votos',
        party_sum: 'Suma partidos', blancos: 'Blancos',
        nulos: 'Nulos', no_marcados: 'No marcados',
        camara_total: 'Total Cámara', senado_total: 'Total Senado',
        sufragantes_e11: 'Sufragantes E-11',
        num_firmas: 'Firmas', min_requerido: 'Mínimo requerido',
        nulo_pct: 'Nulo %', party_name: 'Partido',
        votes: 'Votos', municipio: 'Municipio',
    };
    const skip = new Set(['mesa_id', 'is_pmsn', 'party_code']);
    const parts = [];
    for (const [key, val] of Object.entries(details)) {
        if (skip.has(key) || val === null || val === undefined) continue;
        const label = labels[key] || key;
        const display = typeof val === 'number' && key.includes('pct')
            ? `${val}%` : String(val);
        parts.push(`${label}: ${display}`);
    }
    return parts.join(' | ');
}

function isPmsnParty(name) {
    if (!name) return false;
    const upper = name.toUpperCase().normalize('NFD').replace(/[\u0300-\u036f]/g, '');
    if (upper.includes('NUEVO LIBERALISMO')) return false;
    return upper.includes('SALVACION') || upper.includes('PMSN');
}

function renderPartyRow(p) {
    const name = cleanPartyName(p.party_name);
    const pmsn = isPmsnParty(p.party_name);
    const bg = pmsn ? 'background: rgba(201, 168, 76, 0.2);' : '';
    const textStyle = pmsn
        ? 'font-weight: 700; text-decoration: underline;' : '';
    return `<tr style="border-bottom: 1px solid var(--border-light, #ddd); ${bg}">
        <td style="padding: 0.3rem; max-width: 200px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; color: var(--text, #111); ${textStyle}">${escapeHtml(name)}${pmsn ? ' <span style="font-size:0.6rem; background:#C9A84C; color:#fff; padding:0.1rem 0.3rem; border-radius:3px;">PMSN</span>' : ''}</td>
        <td style="text-align: right; padding: 0.3rem; color: var(--text, #111); ${textStyle}">${(p.votes || 0).toLocaleString()}</td>
    </tr>`;
}

function renderE14Matrix(detail) {
    const partidos = detail.partidos || [];
    const partySum = partidos.reduce((s, p) => s + (p.votes || 0), 0);
    const blancos = detail.votos_blancos != null ? detail.votos_blancos : null;
    const nulos = detail.votos_nulos != null ? detail.votos_nulos : null;
    const noMarcados = detail.votos_no_marcados != null ? detail.votos_no_marcados : null;
    const totalDeclarado = detail.total_votos || 0;

    const fullSum = partySum + (blancos ?? 0) + (nulos ?? 0) + (noMarcados ?? 0);
    const diff = fullSum - totalDeclarado;
    const partySumExceedsTotal = totalDeclarado > 0 && partySum > totalDeclarado;
    const totalMatch = totalDeclarado > 0 && diff === 0;

    const tdBase = 'padding: 0.3rem 0.5rem;';
    const thBase = 'padding: 0.3rem 0.5rem; color: var(--text); font-weight: 600; font-size: 0.75rem; text-transform: uppercase; letter-spacing: 0.04em;';

    // Nivelación section
    const sufragantes = detail.sufragantes_e11 != null ? detail.sufragantes_e11 : '—';
    const votosUrna = detail.votos_en_urna != null ? detail.votos_en_urna : '—';
    const nivelaHtml = `
        <div style="display: flex; gap: 1.5rem; padding: 0.5rem 0.75rem; background: var(--surface-secondary, #f5f5f5); border-radius: 6px; margin-bottom: 0.75rem; font-size: 0.8rem; color: var(--text-secondary, #555);">
            <span>Sufragantes E-11: <b style="color: var(--text, #111);">${sufragantes}</b></span>
            <span>Votos en Urna: <b style="color: var(--text, #111);">${votosUrna}</b></span>
        </div>`;

    // Códigos de circunscripción especial de comunidades indígenas (SENADO)
    const INDIGENOUS_CODES = new Set([
        '0143','0156','0166','0167','0177','0181','0186','0203'
    ]);
    const INDIGENOUS_SEP = `<tr style="background:#f0f0f0; border-top: 2px solid #aaa; border-bottom: 2px solid #aaa;">
        <td colspan="3" style="padding:0.3rem 0.5rem; font-size:0.7rem; font-weight:700;
            text-transform:uppercase; letter-spacing:0.06em; color:#555; text-align:center;">
            Circunscripción Especial de Comunidades Indígenas
        </td>
    </tr>`;

    // Party rows (with indigenous separator injected before first indigenous code)
    let indigenousSepInserted = false;
    const partyRowsHtml = partidos.map(p => {
        const pmsn = isPmsnParty(p.party_name);
        // Fallback: use original name if cleanPartyName strips it (e.g. short names like "ADA")
        const name = cleanPartyName(p.party_name) || (p.party_name ? p.party_name.slice(0, 40) : '');

        const rowBg = pmsn ? 'background: rgba(201, 168, 76, 0.2);' : '';
        const textStyle = pmsn ? 'font-weight: 700; text-decoration: underline;' : '';
        const codeStr = p.party_code ? String(p.party_code).padStart(4, '0') : '';
        const code = codeStr ? escapeHtml(codeStr) : '—';
        const pmsnBadge = pmsn ? '<span style="font-size:0.6rem; background:#C9A84C; color:#fff; padding:0.1rem 0.3rem; border-radius:3px; margin-left:3px;">PMSN</span>' : '';
        let sep = '';
        if (!indigenousSepInserted && codeStr && INDIGENOUS_CODES.has(codeStr)) {
            sep = INDIGENOUS_SEP;
            indigenousSepInserted = true;
        }

        // Show vote count with OCR correction indicators
        let votesDisplay;
        const _votes = p.votes || 0;
        const _ocr   = p.total_votes_ocr;
        const _hasOcrDiff = _ocr != null && _ocr !== _votes;

        if (p._correction && p._correction.original_votes != null && p._correction.original_votes !== _votes) {
            // Caso C: capeado por E11 — LLM corrigió a 0
            const orig   = p._correction.original_votes;
            const reason = p._correction.reason || 'supera total del acta';
            votesDisplay = `<span style="color:#b7600a; font-weight:700;">0</span>`
                + ` <span title="OCR leía ${orig.toLocaleString()} → corregido a 0 (${reason})" style="cursor:help; color:#b7600a;">⚠</span>`;
        } else if (_hasOcrDiff && p.audit_adjusted) {
            // Caso B: LLM auditó y corrigió
            votesDisplay = `<span style="font-weight:700;">${_votes.toLocaleString()}</span>`
                + ` <span title="OCR leía ${_ocr.toLocaleString()} → LLM auditó y corrigió a ${_votes.toLocaleString()}" style="cursor:help; color:#2e7d32; font-size:0.9em;">✓</span>`;
        } else if (_hasOcrDiff || p.needs_review) {
            // Caso A: discrepancia sin resolver o requiere revisión manual
            const tip = _hasOcrDiff
                ? `OCR leía ${_ocr.toLocaleString()} → ajustado a ${_votes.toLocaleString()} (pendiente revisión)`
                : 'Requiere revisión manual';
            votesDisplay = `<span style="font-weight:700;">${_votes.toLocaleString()}</span>`
                + ` <span title="${tip}" style="cursor:help; color:#b7600a; font-size:0.9em;">⚠</span>`;
        } else {
            // Caso D: sin discrepancia
            votesDisplay = _votes.toLocaleString();
        }

        return sep + `<tr style="border-bottom: 1px solid var(--border-light, #e8e8e8); ${rowBg}">
            <td style="${tdBase} color: var(--text-secondary, #888); font-family: monospace; font-size: 0.75rem; white-space: nowrap;">${code}</td>
            <td style="${tdBase} max-width: 200px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; color: var(--text, #111); ${textStyle}">${escapeHtml(name)}${pmsnBadge}</td>
            <td style="${tdBase} text-align: right; color: var(--text, #111); ${textStyle}">${votesDisplay}</td>
        </tr>`;
    }).join('');

    // PMSN missing warning: only for SENADO — CAMARA may legitimately not have PMSN
    const hasPmsn = partidos.some(p => isPmsnParty(p.party_name));
    const isSenado = (detail.header?.corporacion || '').toUpperCase().includes('SEN');
    const pmsnMissingRow = (!hasPmsn && isSenado) ? `<tr style="border-bottom: 1px solid var(--border-light, #e8e8e8); background: rgba(201, 168, 76, 0.06);">
        <td style="${tdBase} color: var(--text-secondary, #bbb); font-family: monospace; font-size: 0.75rem;">—</td>
        <td style="${tdBase} color: var(--text-secondary, #bbb); font-style: italic; font-size: 0.78rem;">MOV. SALVACIÓN NACIONAL <span style="font-size:0.6rem; background:#aaa; color:#fff; padding:0.1rem 0.3rem; border-radius:3px; margin-left:3px;">No extraído OCR</span></td>
        <td style="${tdBase} text-align: right; color: var(--text-secondary, #bbb);">—</td>
    </tr>` : '';

    // Summary rows
    const partySumColor = partySumExceedsTotal ? '#c0392b' : 'var(--text, #111)';
    const partySumBadge = partySumExceedsTotal
        ? ' <span style="font-size:0.6rem; background:#c0392b; color:#fff; padding:0.1rem 0.3rem; border-radius:3px;">⚠ excede total</span>'
        : '';

    const fullSumColor = totalDeclarado === 0 ? 'var(--text, #111)' : (totalMatch ? '#2D7A3E' : '#b7600a');
    const fullSumSuffix = totalDeclarado === 0 ? ''
        : totalMatch ? ' <span style="font-size:0.7rem; color:#2D7A3E;">✓</span>'
        : ` <span style="font-size:0.7rem; color:#b7600a;">(diff ${diff > 0 ? '+' : ''}${diff})</span>`;

    const totalDeclaradoColor = totalDeclarado === 0 ? 'var(--text-secondary, #888)' : 'var(--text, #111)';
    const totalDeclaradoBadge = totalDeclarado === 0
        ? ' <span style="font-size:0.6rem; background:#aaa; color:#fff; padding:0.1rem 0.3rem; border-radius:3px;">No extraído</span>'
        : '';

    const specialRow = (label, value) => {
        const display = value != null ? value.toLocaleString() : '<span style="color:var(--text-secondary,#aaa);">—</span>';
        return `<tr style="border-bottom: 1px solid var(--border-light, #e8e8e8);">
            <td colspan="2" style="${tdBase} color: var(--text-secondary, #666);">${label}</td>
            <td style="${tdBase} text-align: right; color: var(--text, #111);">${display}</td>
        </tr>`;
    };

    const firmas = detail.num_firmas;
    const firmasDisplay = firmas != null
        ? `${firmas}/6${firmas < 6 ? ' <span style="color:#c0392b;">⚠</span>' : ' <span style="color:#2D7A3E;">✓</span>'}`
        : '<span style="color:var(--text-secondary,#aaa);">—</span>';

    const summaryHtml = `
        <tr style="border-top: 2px solid var(--border, #ccc); background: var(--surface-secondary, #f9f9f9);">
            <td colspan="2" style="${tdBase} font-weight: 600; font-size: 0.78rem; color: ${partySumColor};">Subtotal partidos${partySumBadge}</td>
            <td style="${tdBase} text-align: right; font-weight: 700; color: ${partySumColor};">${partySum.toLocaleString()}</td>
        </tr>
        ${specialRow('Votos en Blanco', blancos)}
        ${specialRow('Votos Nulos', nulos)}
        ${specialRow('No Marcados', noMarcados)}
        <tr style="border-bottom: 1px solid var(--border-light, #e8e8e8);">
            <td colspan="2" style="${tdBase} color: var(--text-secondary, #666);">Firmas de jurados</td>
            <td style="${tdBase} text-align: right;">${firmasDisplay}</td>
        </tr>
        <tr style="border-top: 2px solid var(--border, #ccc); background: var(--surface-secondary, #f5f5f5);">
            <td colspan="2" style="${tdBase} font-weight: 700; font-size: 0.82rem; color: ${fullSumColor};">Total Calculado${fullSumSuffix}</td>
            <td style="${tdBase} text-align: right; font-weight: 700; color: ${fullSumColor};">${fullSum.toLocaleString()}</td>
        </tr>
        <tr style="background: var(--surface-secondary, #f5f5f5);">
            <td colspan="2" style="${tdBase} color: ${totalDeclaradoColor};">Total Declarado (OCR)${totalDeclaradoBadge}</td>
            <td style="${tdBase} text-align: right; color: ${totalDeclaradoColor};">${totalDeclarado > 0 ? totalDeclarado.toLocaleString() : '0'}</td>
        </tr>`;

    return `${nivelaHtml}
        <table style="width: 100%; font-size: 0.8rem; border-collapse: collapse; border: 1px solid var(--border-light, #ddd); border-radius: 6px; overflow: hidden;">
            <thead>
                <tr style="border-bottom: 2px solid var(--border, #ccc); background: var(--surface-secondary, #f5f5f5);">
                    <th style="${thBase} width: 52px;">Código</th>
                    <th style="${thBase} text-align: left;">Partido / Lista</th>
                    <th style="${thBase} text-align: right;">Votos</th>
                </tr>
            </thead>
            <tbody>
                ${partyRowsHtml}
                ${pmsnMissingRow}
                ${summaryHtml}
            </tbody>
        </table>`;
}

function mapIncidentToCPACA(incident) {
    const riskType = (incident.risk_type || '').toUpperCase();
    if (riskType === 'R_ALTO') return '275';  // Art. 275 - Posible nulidad
    if (riskType === 'R_MEDIO') return '225'; // Art. 225 - Reclamable
    return '226'; // Art. 226 - Observación
}

function getCPACAColor(art) {
    const colors = { '275': '#C0253A', '225': '#8B3A5A', '226': '#7A7F85' };
    return colors[art] || '#666';
}

function handleIncidentAction(incidentId, mesaId, action) {
    if (!action) return;
    if (action === 'send-witness') {
        enviarTestigoARevision(incidentId, mesaId);
        return;
    }
    if (action === 'legal-incident') {
        createLegalIncidentFromIncident(incidentId);
    }
}

async function createLegalIncidentFromIncident(incidentId) {
    const reason = 'Creado desde Mesas con Incidencias';
    try {
        const response = await fetch(`/api/incidents/${incidentId}/escalate`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ reason, to_legal: true })
        });
        const data = await response.json();
        if (!data.success) {
            alert(`Error creando incidente jurídico: ${data.error || 'Error desconocido'}`);
            return;
        }
        // Litigio tab removed — stay on contienda
        document.querySelector('[data-tab="contienda"]')?.click();
    } catch (error) {
        console.error('Error creating legal incident:', error);
    }
}

// Incident Modal Functions
window.openIncidentDetail = async function(incidentId) {
    selectedIncidentId = incidentId;
    const incident = allIncidents.find(i => i.id === incidentId);

    if (!incident) {
        console.error('Incident not found:', incidentId);
        return;
    }

    // Populate modal
    const riskActaLevel = getRiskActaLevel(incident);
    const riskActaLabel = riskActaLevel.toUpperCase();
    document.getElementById('incident-modal-id').textContent = `#${incident.id}`;
    document.getElementById('incident-modal-severity').textContent = riskActaLabel;
    document.getElementById('incident-modal-severity').className = `severity-badge ${riskActaLevel}`;
    document.getElementById('incident-modal-type').textContent = `${incident.rule_id || incident.incident_type} — ${incident.risk_label || ''}`;
    document.getElementById('incident-modal-mesa').textContent = incident.mesa_id;
    document.getElementById('incident-modal-location').textContent =
        `${resolveDeptName(incident)} > ${resolveMuniName(incident)} > ${incident.puesto || '--'}`;
    const detailsText = formatPmsnDetails(incident.details);
    document.getElementById('incident-modal-description').textContent =
        `${incident.description}${detailsText ? '\n\n' + detailsText : ''}`;
    document.getElementById('incident-modal-confidence').textContent =
        incident.ocr_confidence ? `${(incident.ocr_confidence * 100).toFixed(0)}%` : 'N/A';
    document.getElementById('incident-modal-sla').textContent = formatSlaTime(incident.sla_remaining_minutes);
    document.getElementById('incident-modal-status').textContent = incident.status;
    document.getElementById('incident-notes').value = incident.resolution_notes || '';

    // Show modal
    document.getElementById('incident-modal').classList.add('active');
};

window.closeIncidentModal = function() {
    document.getElementById('incident-modal').classList.remove('active');
    selectedIncidentId = null;
};

window.assignIncident = async function() {
    if (!selectedIncidentId) return;

    const notes = document.getElementById('incident-notes').value;
    const userId = 'current_user'; // In production, get from session

    try {
        const response = await fetch(`/api/incidents/${selectedIncidentId}/assign`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ user_id: userId, notes: notes })
        });

        const data = await response.json();
        if (data.success) {
            closeIncidentModal();
            loadIncidents();
            alert('Incidente asignado correctamente');
        } else {
            alert('Error asignando incidente: ' + data.error);
        }
    } catch (error) {
        console.error('Error assigning incident:', error);
        alert('Error de conexión');
    }
};

window.resolveIncident = async function() {
    if (!selectedIncidentId) return;

    const notes = document.getElementById('incident-notes').value;
    if (!notes.trim()) {
        alert('Por favor agregue notas de resolución');
        return;
    }

    try {
        const response = await fetch(`/api/incidents/${selectedIncidentId}/resolve`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ resolution: 'RESOLVED', notes: notes })
        });

        const data = await response.json();
        if (data.success) {
            closeIncidentModal();
            loadIncidents();
            alert('Incidente resuelto correctamente');
        } else {
            alert('Error resolviendo incidente: ' + data.error);
        }
    } catch (error) {
        console.error('Error resolving incident:', error);
        alert('Error de conexión');
    }
};

window.refreshIncidents = function() {
    loadIncidents();
    loadWarRoomKPIs();
    timelineCountdown = 30;
};

// ============================================================
// CHOROPLETH MAP FUNCTIONALITY
// ============================================================

let selectedDepartment = null;
let colombiaMap = null;
let geoJsonLayer = null;
let markersLayer = null;
let currentMapMode = 'risk';

// Initialize map when DOM is ready — triggered from tab activation
// Bounds de Colombia: SW [-4.2, -79.0] → NE [12.5, -66.8]
const COLOMBIA_BOUNDS = [[-4.2, -79.0], [12.5, -66.8]];

function initColombiaMap() {
    const mapContainer = document.getElementById('colombia-map');
    if (!mapContainer || colombiaMap) return;

    colombiaMap = L.map('colombia-map', {
        center: [4.5, -74.0],
        zoom: 6,
        minZoom: 5,
        maxZoom: 10,
        zoomControl: true,
        attributionControl: false,
        scrollWheelZoom: true,
        maxBounds: COLOMBIA_BOUNDS,
        maxBoundsViscosity: 1.0
    });

    L.tileLayer('https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png', {
        maxZoom: 10,
        opacity: 0.5
    }).addTo(colombiaMap);

    loadChoroplethData('risk');
    setupMapModeSelector();
}

function setupMapModeSelector() {
    document.querySelectorAll('.map-mode-btn').forEach(btn => {
        btn.addEventListener('click', () => {
            document.querySelectorAll('.map-mode-btn').forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            currentMapMode = btn.dataset.mode;
            loadChoroplethData(currentMapMode);
            updateMapLegend(currentMapMode);
        });
    });
}

async function loadChoroplethData(mode) {
    try {
        const response = await fetch(`/api/geography/choropleth?mode=${mode}`);
        const data = await response.json();
        if (data.success) {
            renderChoropleth(data);
        } else {
            console.error('Error loading choropleth:', data.error);
        }
    } catch (error) {
        console.error('Error fetching choropleth data:', error);
    }
}

function renderChoropleth(data) {
    if (!colombiaMap) return;

    if (geoJsonLayer) colombiaMap.removeLayer(geoJsonLayer);
    if (markersLayer) { colombiaMap.removeLayer(markersLayer); markersLayer = null; }

    // Accept either plain FeatureCollection or wrapped API payload.
    const fc = (data && data.type === 'FeatureCollection')
        ? data
        : {
            type: 'FeatureCollection',
            features: Array.isArray(data?.features) ? data.features : []
        };

    // Choropleth: polígonos rellenos con color por departamento
    geoJsonLayer = L.geoJSON(fc, {
        style: styleDepartment,
        onEachFeature: onEachDepartment
    }).addTo(colombiaMap);

    // Restaurar highlight del departamento seleccionado tras recargar
    if (selectedDepartment) {
        geoJsonLayer.eachLayer(layer => {
            if (layer.feature?.properties?.code === selectedDepartment) {
                layer.setStyle({ weight: 2.5, color: '#C9A227', fillOpacity: 1 });
                layer.bringToFront();
            }
        });
    }

    // Ajustar bounds a Colombia solo en la primera carga
    if (!colombiaMap._castorBoundsSet) {
        colombiaMap.fitBounds(COLOMBIA_BOUNDS, { padding: [10, 10] });
        colombiaMap._castorBoundsSet = true;
    }
}

function styleDepartment(feature) {
    const props = feature.properties || {};
    const metrics = props.metrics || {};
    const hasData = metrics.has_data !== false;
    const color = hasData ? (props.fill_color || getColorForValue(metrics.value || 0)) : '#3a3a3a';
    return {
        fillColor: color,
        fillOpacity: hasData ? 0.85 : 0.55,
        weight: hasData ? 1.2 : 1.6,
        color: hasData ? '#1a1a1a' : '#6a6a6a',
        opacity: 0.95
    };
}

function onEachDepartment(feature, layer) {
    const props = feature.properties || {};
    layer.on({
        mouseover: (e) => {
            e.target.setStyle({ weight: 2.5, color: '#C9A227', fillOpacity: 1 });
            e.target.bringToFront();
            showDepartmentPreview(props);
        },
        mouseout: (e) => {
            if (selectedDepartment === props.code) {
                // Mantener highlight dorado en el departamento seleccionado
                e.target.setStyle({ weight: 2.5, color: '#C9A227', fillOpacity: 1 });
            } else {
                geoJsonLayer.resetStyle(e.target);
                hideDepartmentPreview();
            }
        },
        click: () => selectDepartment(props.code, props.name)
    });
}

function getCentroid(geometry) {
    if (!geometry || !geometry.coordinates) return null;
    if (geometry.type === 'Polygon') return calculatePolygonCentroid(geometry.coordinates[0]);
    if (geometry.type === 'MultiPolygon') {
        let largestArea = 0, centroid = null;
        geometry.coordinates.forEach(poly => {
            const area = calculatePolygonArea(poly[0]);
            if (area > largestArea) { largestArea = area; centroid = calculatePolygonCentroid(poly[0]); }
        });
        return centroid;
    }
    return null;
}

function calculatePolygonCentroid(coords) {
    let sumLat = 0, sumLng = 0;
    coords.forEach(c => { sumLng += c[0]; sumLat += c[1]; });
    return [sumLat / coords.length, sumLng / coords.length];
}

function calculatePolygonArea(coords) {
    let area = 0;
    for (let i = 0; i < coords.length - 1; i++) {
        area += coords[i][0] * coords[i + 1][1];
        area -= coords[i + 1][0] * coords[i][1];
    }
    return Math.abs(area / 2);
}

function createDepartmentMarker(centroid, props) {
    const metrics = props.metrics || {};
    const hasData = metrics.has_data !== false;
    const color = hasData ? (props.fill_color || getColorForValue(metrics.value || 0)) : '#555';
    const mesas = metrics.mesas_total || 0;
    const radius = hasData ? Math.min(18, Math.max(9, 9 + (mesas / 50))) : 6;
    const fillOpacity = hasData ? 0.9 : 0.3;

    const marker = L.circleMarker(centroid, {
        radius, fillColor: color, fillOpacity,
        color: hasData ? '#1C1C1C' : '#444',
        weight: hasData ? 2 : 1
    });
    marker.deptProps = props;

    marker.on('mouseover', (e) => {
        e.target.setStyle({ radius: radius + 3, fillOpacity: 1, weight: 3, color: '#C9A227' });
        showDepartmentPreview(props);
    });
    marker.on('mouseout', (e) => {
        e.target.setStyle({ radius, fillOpacity, weight: hasData ? 2 : 1, color: hasData ? '#1C1C1C' : '#444' });
        if (selectedDepartment !== props.code) hideDepartmentPreview();
    });
    marker.on('click', () => selectDepartment(props.code, props.name));

    return marker;
}

function getColorForValue(value) {
    if (value >= 80) return '#1E7D4F';
    if (value >= 60) return '#7CB342';
    if (value >= 40) return '#F0C040';
    if (value >= 20) return '#E87020';
    return '#C0253A';
}

function showDepartmentPreview(props) {
    const panel = document.getElementById('dept-info-panel');
    const titleEl = document.getElementById('dept-panel-title');
    const subtitleEl = document.getElementById('dept-panel-subtitle');
    const contentEl = document.getElementById('dept-info-content');
    if (!panel || !props) return;

    const metrics = props.metrics || {};
    const hasData = metrics.has_data !== false;
    titleEl.textContent = props.name || 'Departamento';
    subtitleEl.textContent = `Código: ${props.code || '--'}`;

    if (!hasData) {
        contentEl.innerHTML = `
            <div class="dept-preview-stats">
                <div style="color: var(--muted); font-size: 0.85rem; text-align: center; padding: 1rem 0;">Sin datos E-14 procesados</div>
            </div>
            <div class="dept-preview-hint">Click para ver detalles completos</div>`;
        panel.classList.add('preview-active');
        return;
    }

    const isVotesMode = currentMapMode === 'votes';
    const valueDisplay = isVotesMode ? formatNumber(metrics.value || 0) : `${(metrics.value || 0).toFixed(1)}%`;
    const confDisplay = metrics.avg_confidence ? `${(metrics.avg_confidence * 100).toFixed(0)}%` : '--';
    const confColor = (metrics.avg_confidence || 0) >= OCR_MEDIUM_RISK / 100
        ? 'var(--success, #1E7D4F)'
        : (metrics.avg_confidence || 0) >= OCR_HIGH_RISK / 100
            ? 'var(--warning, #B07D10)'
            : 'var(--danger, #C0253A)';

    contentEl.innerHTML = `
        <div class="dept-preview-stats">
            <div class="dept-stat-row">
                <span class="dept-stat-label">${getModeLabel(currentMapMode)}</span>
                <span class="dept-stat-value">${valueDisplay}</span>
            </div>
            <div class="dept-stat-row">
                <span class="dept-stat-label">Total Votos</span>
                <span class="dept-stat-value">${formatNumber(metrics.total_votos || 0)}</span>
            </div>
            <div class="dept-stat-row">
                <span class="dept-stat-label">Mesas</span>
                <span class="dept-stat-value">${formatNumber(metrics.mesas_total || 0)}</span>
            </div>
            <div class="dept-stat-row">
                <span class="dept-stat-label">Confianza OCR</span>
                <span class="dept-stat-value" style="color: ${confColor}">${confDisplay}</span>
            </div>
            <div class="dept-stat-row">
                <span class="dept-stat-label">Alto Riesgo</span>
                <span class="dept-stat-value ${(metrics.high_risk_count || 0) > 0 ? 'danger' : ''}">${metrics.high_risk_count || 0}</span>
            </div>
            <div class="dept-stat-row">
                <span class="dept-stat-label">Riesgo Medio</span>
                <span class="dept-stat-value ${(metrics.medium_risk_count || 0) > 0 ? 'warning' : ''}">${metrics.medium_risk_count || 0}</span>
            </div>
        </div>
        <div class="dept-preview-hint">Click para ver detalles completos</div>`;

    panel.classList.add('preview-active');
}

function hideDepartmentPreview() {
    const panel = document.getElementById('dept-info-panel');
    if (!panel || selectedDepartment) return;
    panel.classList.remove('preview-active');
    document.getElementById('dept-panel-title').textContent = 'Seleccione un Departamento';
    document.getElementById('dept-panel-subtitle').textContent = 'Hover sobre un punto para vista previa';
    document.getElementById('dept-info-content').innerHTML = `
        <div class="dept-info-empty">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
                <path d="M21 10c0 7-9 13-9 13s-9-6-9-13a9 9 0 0 1 18 0z"/>
                <circle cx="12" cy="10" r="3"/>
            </svg>
            <p>Pase el mouse sobre un punto del mapa para ver vista previa, o haga click para ver detalles completos.</p>
        </div>`;
}

function getModeLabel(mode) {
    return { coverage: 'Cobertura', risk: 'Riesgo', discrepancy: 'Discrepancia', votes: 'Votos' }[mode] || mode;
}

function updateMapLegend(mode) {
    const legend = document.getElementById('map-legend');
    if (!legend) return;
    const noData = '<div class="legend-item"><span class="legend-color" style="background: #555; opacity: 0.3;"></span> Sin datos</div>';

    if (mode === 'coverage') {
        legend.innerHTML = `
            <div class="legend-item"><span class="legend-color" style="background: #1E7D4F;"></span> Alto (&gt;80%)</div>
            <div class="legend-item"><span class="legend-color" style="background: #7CB342;"></span> Medio-Alto (60-80%)</div>
            <div class="legend-item"><span class="legend-color" style="background: #F0C040;"></span> Medio (40-60%)</div>
            <div class="legend-item"><span class="legend-color" style="background: #E87020;"></span> Bajo (20-40%)</div>
            <div class="legend-item"><span class="legend-color" style="background: #C0253A;"></span> Crítico (&lt;20%)</div>
            ${noData}`;
    } else if (mode === 'risk') {
        legend.innerHTML = `
            <div class="legend-item"><span class="legend-color" style="background: #1E7D4F;"></span> Bajo (&lt;2%)</div>
            <div class="legend-item"><span class="legend-color" style="background: #7CB342;"></span> Moderado (2-5%)</div>
            <div class="legend-item"><span class="legend-color" style="background: #F0C040;"></span> Medio (5-10%)</div>
            <div class="legend-item"><span class="legend-color" style="background: #E87020;"></span> Alto (10-15%)</div>
            <div class="legend-item"><span class="legend-color" style="background: #C0253A;"></span> Crítico (&gt;15%)</div>
            ${noData}`;
    } else if (mode === 'discrepancy') {
        legend.innerHTML = `
            <div class="legend-item"><span class="legend-color" style="background: #1E7D4F;"></span> Sin Δ (&lt;2%)</div>
            <div class="legend-item"><span class="legend-color" style="background: #7CB342;"></span> Bajo (2-5%)</div>
            <div class="legend-item"><span class="legend-color" style="background: #F0C040;"></span> Medio (5-10%)</div>
            <div class="legend-item"><span class="legend-color" style="background: #E87020;"></span> Alto (&gt;10%)</div>
            ${noData}`;
    } else if (mode === 'votes') {
        legend.innerHTML = `
            <div class="legend-item"><span class="legend-color" style="background: #7B1FA2;"></span> Líder (&gt;30%)</div>
            <div class="legend-item"><span class="legend-color" style="background: #9C27B0;"></span> Fuerte (20-30%)</div>
            <div class="legend-item"><span class="legend-color" style="background: #BA68C8;"></span> Competitivo (15-20%)</div>
            <div class="legend-item"><span class="legend-color" style="background: #CE93D8;"></span> Moderado (10-15%)</div>
            <div class="legend-item"><span class="legend-color" style="background: #E1BEE7;"></span> Bajo (&lt;10%)</div>
            ${noData}`;
    }
}

function renderDepartmentInfo(stats, incidents) {
    const content = document.getElementById('dept-info-content');
    if (stats.has_data === false) {
        content.innerHTML = '<div style="color: var(--muted); text-align: center; padding: 2rem 1rem; font-size: 0.9rem;">Sin datos E-14 procesados para este departamento.</div>';
        return;
    }

    const p0Class = stats.incidents_p0 > 0 ? 'danger' : '';
    const riskClass = stats.high_risk_count > 5 ? 'danger' : (stats.high_risk_count > 2 ? 'warning' : 'success');
    const confVal = stats.avg_confidence || 0;
    const confDisplay = confVal > 0 ? `${(confVal * 100).toFixed(0)}%` : '--';
    const confClass = confVal >= OCR_MEDIUM_RISK / 100 ? 'success' : (confVal >= OCR_HIGH_RISK / 100 ? 'warning' : 'danger');

    content.innerHTML = `
        <div class="dept-kpis">
            <div class="dept-kpi"><div class="dept-kpi-value">${formatNumber(stats.total_votos || 0)}</div><div class="dept-kpi-label">Total Votos</div></div>
            <div class="dept-kpi"><div class="dept-kpi-value">${formatNumber(stats.mesas_total)}</div><div class="dept-kpi-label">Mesas</div></div>
            <div class="dept-kpi"><div class="dept-kpi-value ${confClass}">${confDisplay}</div><div class="dept-kpi-label">Confianza OCR</div></div>
            <div class="dept-kpi"><div class="dept-kpi-value ${riskClass}">${stats.high_risk_count}</div><div class="dept-kpi-label">Alto Riesgo</div></div>
            <div class="dept-kpi"><div class="dept-kpi-value">${stats.medium_risk_count || 0}</div><div class="dept-kpi-label">Riesgo Medio</div></div>
            <div class="dept-kpi"><div class="dept-kpi-value ${p0Class}">${stats.incidents_p0}</div><div class="dept-kpi-label">P0 Abiertos</div></div>
        </div>
        <div class="dept-section-title">Incidentes Activos</div>
        <div class="dept-incidents-list">
            ${incidents.length > 0 ? incidents.map(inc => `
                <div class="dept-incident-item" style="cursor: pointer;" onclick="openMesaDetailFromIncident('${inc.mesa_id}')">
                    <span class="severity-badge ${inc.severity.toLowerCase()}">${inc.severity}</span>
                    <span class="dept-incident-mesa">${inc.mesa_id}</span>
                    <span class="dept-incident-type">${formatIncidentType(inc.incident_type)}</span>
                </div>`).join('') : '<div style="color: var(--muted); font-size: 0.75rem; padding: 0.5rem;">Sin incidentes activos</div>'}
        </div>
        <div class="dept-section-title">Top Partidos (E-14)</div>
        <div class="dept-incidents-list">
            ${(stats.top_parties || []).map((c, i) => `
                <div class="dept-incident-item">
                    <span style="font-weight: 700; color: var(--accent); width: 20px;">#${i + 1}</span>
                    <span class="dept-incident-mesa">${escapeHtml(c.name)}</span>
                    <span class="dept-incident-type">${c.percentage}%</span>
                </div>`).join('') || '<div style="color: var(--muted); font-size: 0.75rem; padding: 0.5rem;">Sin datos E-14</div>'}
        </div>`;
}

function filterMapByDept() {
    const dept = document.getElementById('map-filter-dept')?.value || '';
    updateMapFilter('dept', dept);
    if (dept) populateMapMuniFilter(dept);
}

function filterMapByMuni() {
    updateMapFilter('muni', document.getElementById('map-filter-muni')?.value || '');
}

function filterMapByZona() {
    updateMapFilter('zona', document.getElementById('map-filter-zona')?.value || '');
}

function filterMapByPuesto() {
    updateMapFilter('puesto', document.getElementById('map-filter-puesto')?.value || '');
}

function populateMapMuniFilter(dept) {
    if (!window.e14LiveData) return;
    const munis = [...new Set(
        (window.e14LiveData.forms || [])
            .filter(f => f.departamento === dept)
            .map(f => f.municipio)
            .filter(Boolean)
    )].sort();
    populateSelect('map-filter-muni', munis);
}

function applyMapFilters() {
    const filters = window.mapFilters || {};
    if (!colombiaMap || Object.keys(filters).every(k => !filters[k])) return;
    loadChoroplethData(currentMapMode);
}

function clearMapFilters() {
    window.mapFilters = {};
    ['map-filter-dept', 'map-filter-muni', 'map-filter-zona', 'map-filter-puesto'].forEach(id => {
        const el = document.getElementById(id);
        if (el) el.value = '';
    });
    loadChoroplethData(currentMapMode);
}

// Store markers layer globally













async function selectDepartment(deptCode, deptName) {
    selectedDepartment = deptCode;

    // Update panel header
    document.getElementById('dept-panel-title').textContent = deptName;
    document.getElementById('dept-panel-subtitle').textContent = `Código: ${deptCode}`;

    // Show loading
    const content = document.getElementById('dept-info-content');
    content.innerHTML = '<div class="dept-info-empty"><div class="loading-spinner" style="width: 32px; height: 32px;"></div><p>Cargando datos...</p></div>';

    try {
        // Fetch stats and incidents in parallel
        const [statsResponse, incidentsResponse] = await Promise.all([
            fetch(`/api/geography/department/${deptCode}/stats`),
            fetch(`/api/geography/department/${deptCode}/incidents?limit=5`)
        ]);

        const statsData = await statsResponse.json();
        const incidentsData = await incidentsResponse.json();

        if (statsData.success && incidentsData.success) {
            renderDepartmentInfo(statsData.stats, incidentsData.incidents);
        } else {
            content.innerHTML = '<div class="dept-info-empty"><p>Error cargando datos del departamento</p></div>';
        }
    } catch (error) {
        console.error('Error loading department data:', error);
        content.innerHTML = '<div class="dept-info-empty"><p>Error de conexión</p></div>';
    }
}


// ============================================================
// MESA DETAIL MODAL FUNCTIONALITY
// ============================================================

let currentMesaDetail = null;

window.openMesaDetailFromIncident = function(mesaId) {
    openMesaDetail(mesaId);
};

async function openMesaDetail(mesaId) {
    markMesaAsSeen(mesaId);
    document.querySelectorAll(`.badge-nueva[data-mesa="${mesaId}"]`).forEach(el => el.remove());

    currentMesaDetail = null;

    // Show modal with loading state
    document.getElementById('mesa-detail-modal').classList.add('active');
    document.getElementById('mesa-detail-id').textContent = mesaId;
    document.getElementById('mesa-detail-location').textContent = 'Cargando...';
    document.getElementById('mesa-detail-status').textContent = '...';
    document.getElementById('mesa-detail-confidence').textContent = '--%';
    const juridicalEl = document.getElementById('mesa-juridical-obs');
    if (juridicalEl) juridicalEl.innerHTML = '<div style="color: var(--muted); font-size: 0.8rem;">Cargando...</div>';

    try {
        // Try E14 JSON store first (has raw_text for litigation evidence)
        const isNumericId = /^\d+$/.test(String(mesaId));
        const e14Url = isNumericId
            ? `/api/e14-data/form/${mesaId}`
            : `/api/e14-data/form-by-mesa/${mesaId}`;
        const e14Resp = await fetch(e14Url);

        if (e14Resp.ok) {
            const formData = await e14Resp.json();
            if (formData && !formData.error) {
                currentMesaDetail = transformE14ToDetail(formData);
                renderMesaDetail(currentMesaDetail);
                return;
            }
        }

        // Fallback to campaign-team endpoint
        const response = await fetch(`/api/campaign-team/mesa/${mesaId}/detail`);
        const data = await response.json();
        if (data.success) {
            currentMesaDetail = data.detail;
            renderMesaDetail(data.detail);
        } else {
            alert('Error cargando detalles de la mesa: ' + (data.error || 'desconocido'));
            closeMesaDetailModal();
        }
    } catch (error) {
        console.error('Error loading mesa detail:', error);
        alert('Error de conexión');
        closeMesaDetailModal();
    }
}

function transformE14ToDetail(form) {
    const conf = form.ocr_confidence || 0;
    const confPct = conf * 100;
    const status = confPct >= OCR_MEDIUM_RISK ? 'VALIDATED' : (confPct >= OCR_HIGH_RISK ? 'NEEDS_REVIEW' : 'HIGH_RISK');
    const partidos = form.partidos || [];
    const partySum = partidos.reduce((s, p) => s + (p.votes || 0), 0);
    const blancos = form.votos_blancos || 0;
    const nulos = form.votos_nulos || 0;
    const noMarcados = form.votos_no_marcados || 0;
    const fullSum = partySum + blancos + nulos + noMarcados;
    const hasArithError = fullSum > 0 && form.total_votos > 0
        && Math.abs(fullSum - form.total_votos) > ARITH_WARN_TOL;  // fórmula: partidos+blancos+nulos+no_marcados=total

    // Bug 4 — compute a short explanation for the OCR confidence value
    let confidence_reason = null;
    if (form.total_votos === 0 && partySum > 0) {
        confidence_reason = 'Total votos no legible';
    } else if (form.sufragantes_e11 == null) {
        confidence_reason = 'Sufragantes E-11 no extraídos';
    } else if (conf < 0.70) {
        confidence_reason = 'Confianza de partidos baja (OCR)';
    }

    // Bug 7 — warn when sufragantes_e11 is missing so PMSN-04 can't fire
    const baseWarnings = form.warnings || [];
    const warnings = form.sufragantes_e11 == null
        ? [...baseWarnings, 'Sufragantes E-11 no extraídos — PMSN-04 no evaluada']
        : baseWarnings;

    return {
        mesa_id: form.mesa_id || String(form.id),
        form_id: form.id,
        header: {
            departamento: form.departamento || '',
            municipio: form.municipio || '',
            puesto: form.puesto_nombre || form.lugar || form.puesto || form.puesto_cod || '',  // Bug 1
            zona: form.zona_cod || form.zona || '',
            mesa_number: form.mesa_num || form.mesa || '',
            corporacion: form.corporacion || '',
        },
        status: status,
        overall_confidence: conf,
        confidence_reason: confidence_reason,  // Bug 4
        raw_text: form.raw_text || '',
        partidos: partidos,
        ocr_fields: (() => {
            const totalVotosUnread = (form.total_votos === 0 || form.total_votos == null) && partySum > 0;
            const sufE11 = form.sufragantes_e11;
            const sufE11Bad = sufE11 == null || (typeof sufE11 === 'number' && Number.isNaN(sufE11));
            return [
                { label: 'Total Votos', value: totalVotosUnread ? 'N/D' : (form.total_votos || 0),
                  confidence: totalVotosUnread ? 0 : conf,
                  needs_review: totalVotosUnread || confPct < OCR_LEGIBILITY },
                { label: 'Votos Blancos', value: form.votos_blancos || 0, confidence: conf, needs_review: false },
                { label: 'Votos Nulos', value: form.votos_nulos || 0, confidence: conf, needs_review: false },
                { label: 'Suma Partidos', value: partySum, confidence: conf, needs_review: false },
                { label: 'Suma Total (partidos+blancos+nulos+no_marcados)', value: fullSum, confidence: hasArithError ? 0.3 : conf, needs_review: hasArithError },
                { label: 'Sufragantes E-11', value: sufE11Bad ? 'N/D' : sufE11,
                  confidence: conf, needs_review: sufE11Bad },
            ];
        })(),
        validations: [
            { check: 'Suma (partidos+blancos+nulos+no_marcados) = Total votos', passed: !hasArithError, detail: hasArithError ? `FALLO - (${partySum}+${blancos}+${nulos}+${noMarcados})=${fullSum} vs total=${form.total_votos} (dif: ${Math.abs(fullSum - form.total_votos)})` : 'OK' },
            { check: 'Legibilidad OCR', passed: confPct >= OCR_LEGIBILITY, detail: `${confPct.toFixed(0)}%${confPct >= OCR_LEGIBILITY && hasArithError ? ' (texto legible pero suma incorrecta)' : ''}` },
            { check: 'Partidos detectados', passed: partidos.length >= 3, detail: `${partidos.length} partidos` },
            ...(hasArithError && confPct >= OCR_LEGIBILITY ? [{ check: 'Tipo de anomalia', passed: false, detail: `Error ARITMETICO (no de OCR): partidos(${partySum}) + blancos(${blancos}) + nulos(${nulos}) + no_marcados(${noMarcados}) = ${fullSum} ≠ total(${form.total_votos}). Art. 275 num. 3 CPACA — Falsedad en documentos electorales.` }] : []),
        ],
        comparison: [],
        warnings: warnings,  // Bug 7
        incidents: [],
        pdf_url: form.id ? `/api/e14-data/pdf/${form.id}` : null,
        pmsn_alerts: form.pmsn_alerts || [],
        // Fields for Matriz E-14 (preserve null to distinguish "0 OCR" vs "no extraído")
        total_votos: form.total_votos ?? 0,
        votos_blancos: form.votos_blancos ?? null,
        votos_nulos: form.votos_nulos ?? null,
        votos_no_marcados: form.votos_no_marcados ?? null,
        sufragantes_e11: form.sufragantes_e11 ?? null,
        votos_en_urna: form.votos_en_urna ?? null,
    };
}

window.closeMesaDetailModal = function() {
    document.getElementById('mesa-detail-modal').classList.remove('active');
    currentMesaDetail = null;
};

function renderMesaDetail(detail) {
    // Header — show human-readable location
    const headerDept = normalizeLocationName(detail.header.dept_name || detail.header.departamento || resolveDeptName(detail.header));
    const headerMuni = normalizeLocationName(detail.header.muni_name || detail.header.municipio || resolveMuniName(detail.header));
    const headerPuesto = detail.header.puesto || '--';
    const headerZona = detail.header.zona ? `Z${String(detail.header.zona).padStart(2, '0')}` : '';
    const headerMesa = detail.header.mesa_number || resolveMesaLabel({ mesa_id: detail.mesa_id });
    const locationStr = [headerDept, headerMuni, headerPuesto, headerZona ? `${headerZona} / Mesa ${headerMesa}` : `Mesa ${headerMesa}`].filter(Boolean).join(' > ');
    document.getElementById('mesa-detail-id').textContent = locationStr;
    document.getElementById('mesa-detail-location').textContent =
        `${detail.header.corporacion || ''} | Mesa ID: ${detail.mesa_id}`;

    // Status badge
    const statusEl = document.getElementById('mesa-detail-status');
    statusEl.textContent = detail.status.replace('_', ' ');
    statusEl.className = 'mesa-status-badge';
    if (detail.status === 'VALIDATED') statusEl.classList.add('validated');
    else if (detail.status === 'NEEDS_REVIEW') statusEl.classList.add('needs-review');
    else statusEl.classList.add('high-risk');

    // Confidence
    const confEl = document.getElementById('mesa-detail-confidence');
    const confPct = (detail.overall_confidence * 100).toFixed(0);
    confEl.textContent = `${confPct}%`;
    confEl.className = 'mesa-confidence-value';
    confEl.classList.add(confidenceClass(detail.overall_confidence * 100));

    // Bug 4 — show confidence reason below the percentage
    const confReasonId = 'mesa-detail-confidence-reason';
    let confReasonEl = document.getElementById(confReasonId);
    if (!confReasonEl) {
        confReasonEl = document.createElement('div');
        confReasonEl.id = confReasonId;
        confReasonEl.style.cssText = 'font-size:0.7rem; color:var(--text-secondary); margin-top:2px;';
        confEl.parentNode.insertBefore(confReasonEl, confEl.nextSibling);
    }
    confReasonEl.textContent = detail.confidence_reason || '';

    // OCR Fields
    renderOcrFields(detail.ocr_fields);

    // E-14 image
    renderMesaE14Image(detail);

    // PMSN rules for this mesa
    renderPmsnRulesForMesa(detail.pmsn_alerts || []);

    // Juridical observations (from litigio anomalies or derived from form data)
    renderMesaJuridicalObs(detail);
}

function _buildPmsnDetails(ruleId, details) {
    if (!details) return '';
    const row = (label, value) =>
        `<div style="display:flex; gap:0.5rem; font-size:0.75rem; padding:1px 0;">
            <span style="color:var(--text-secondary); min-width:130px;">${label}</span>
            <span style="font-weight:600; color:var(--text);">${value}</span>
        </div>`;
    const rows = [];

    if (details.ocr_noise_suspected) {
        rows.push(`<div style="display:inline-block; font-size:0.7rem; font-weight:700;
            background:#F59E0B22; color:#B45309; border:1px solid #F59E0B55;
            border-radius:4px; padding:1px 6px; margin-bottom:4px;">⚠ Posible ruido OCR</div>`);
    }

    if (ruleId === 'PMSN-01') {
        if (details.camara_total !== undefined) rows.push(row('Cámara total', details.camara_total));
        if (details.senado_total !== undefined) rows.push(row('Senado total', details.senado_total));
        if (details.diff_pct     !== undefined) rows.push(row('Diferencia', `${details.diff_pct}%`));
    } else if (ruleId === 'PMSN-02') {
        if (details.party_name !== undefined) rows.push(row('Partido', details.party_name));
        if (details.votes      !== undefined) rows.push(row('Votos', details.votes));
        if (details.is_pmsn    !== undefined) rows.push(row('Es partido PMSN', details.is_pmsn ? 'Sí' : 'No'));
    } else if (ruleId === 'PMSN-03') {
        if (details.computed_sum  !== undefined) rows.push(row('Suma partidos (OCR)', details.computed_sum));
        if (details.total_votos   !== undefined) rows.push(row('Total declarado', details.total_votos));
        if (details.diff          !== undefined) rows.push(row('Diferencia (diff)', details.diff));
        if (details.blancos       !== undefined) rows.push(row('Blancos', details.blancos));
        if (details.nulos         !== undefined) rows.push(row('Nulos', details.nulos));
        if (details.no_marcados   !== undefined) rows.push(row('No marcados', details.no_marcados));
    } else if (ruleId === 'PMSN-04') {
        if (details.sufragantes_e11 !== undefined) rows.push(row('Sufragantes E-11', details.sufragantes_e11));
        if (details.total_votos     !== undefined) rows.push(row('Total votos E-14', details.total_votos));
        if (details.diff            !== undefined) rows.push(row('Diferencia', details.diff));
    } else if (ruleId === 'PMSN-05') {
        if (details.pmsn_votes !== undefined) rows.push(row('Votos PMSN', details.pmsn_votes));
        if (details.municipio  !== undefined) rows.push(row('Municipio pareto', details.municipio));
    } else if (ruleId === 'PMSN-06') {
        if (details.num_firmas    !== undefined) rows.push(row('Firmas encontradas', details.num_firmas));
        if (details.min_requerido !== undefined) rows.push(row('Mínimo requerido', details.min_requerido));
    } else if (ruleId === 'PMSN-07') {
        if (details.nulo_pct    !== undefined) rows.push(row('% Nulos', `${details.nulo_pct}%`));
        if (details.votos_nulos !== undefined) rows.push(row('Votos nulos', details.votos_nulos));
        if (details.total_votos !== undefined) rows.push(row('Total votos', details.total_votos));
    }

    if (rows.length === 0) return '';
    return `<div style="margin-top:6px; padding:6px 8px; background:var(--bg, #f9f9f7);
        border-radius:4px; border:1px solid var(--border, #e5e5e5);">
        ${rows.join('')}
    </div>`;
}

function renderPmsnRulesForMesa(alerts) {
    const container = document.getElementById('mesa-pmsn-rules');
    if (!container) return;

    if (!alerts || alerts.length === 0) {
        container.innerHTML = '<div style="color: var(--muted); text-align: center; font-size: 0.85rem;">Sin alertas PMSN para esta mesa</div>';
        return;
    }

    const riskColors = { 'R_ALTO': '#E05252', 'R_MEDIO': '#F07030', 'R_BAJO': '#D4A017' };
    container.innerHTML = alerts.map(a => {
        const color = riskColors[a.risk_type] || '#777';
        const pmsnPartyLabel = (a.pmsn_party_name && a.pmsn_party_votes > 0)
            ? ` · ${a.pmsn_party_name} (${a.pmsn_party_votes} OCR)`
            : '';
        const pmsnVotesBadge = (a.pmsn_votes !== undefined)
            ? `<span style="font-size:0.65rem; padding:1px 6px; border-radius:10px;
                background:${a.pmsn_relevant ? '#16A34A22' : '#77777722'};
                color:${a.pmsn_relevant ? '#15803D' : '#555'}; border:1px solid ${a.pmsn_relevant ? '#86EFAC' : '#ccc'};">
                ${a.pmsn_votes} voto${a.pmsn_votes !== 1 ? 's' : ''} PMSN${pmsnPartyLabel} · ${a.pmsn_relevant ? 'Relevante' : 'Sin votos PMSN'}
               </span>`
            : '';
        const detailsHtml = _buildPmsnDetails(a.rule_id, a.details);
        return `<div style="padding:0.5rem; margin-bottom:0.5rem; background:${color}11;
            border-left:3px solid ${color}; border-radius:4px;">
            <div style="display:flex; justify-content:space-between; align-items:center; gap:0.4rem; flex-wrap:wrap;">
                <span style="font-size:0.7rem; font-weight:700; color:${color};">${a.rule_id}</span>
                <span style="font-size:0.75rem; font-weight:600; color:var(--text); flex:1;">${a.risk_label || ''}</span>
                ${pmsnVotesBadge}
            </div>
            <div style="font-size:0.78rem; color:var(--text-secondary); margin-top:3px;">${a.description || ''}</div>
            ${detailsHtml}
        </div>`;
    }).join('');
}

function renderMesaE14Image(detail) {
    const container = document.getElementById('mesa-e14-image');
    if (!container) return;

    let html = '';

    // 1. PDF viewer (primary evidence)
    if (detail.pdf_url || detail.form_id) {
        const pdfSrc = detail.pdf_url || `/api/e14-data/pdf/${detail.form_id}`;
        html += `<div style="margin-bottom: 1rem;">
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.5rem;">
                <h4 style="margin: 0; color: #111; font-size: 0.9rem;">Documento E-14 Original (PDF)</h4>
                <a href="${pdfSrc}" download="E14_${detail.mesa_id || detail.form_id}.pdf" style="display: inline-flex; align-items: center; gap: 0.3rem; padding: 0.3rem 0.75rem; background: var(--accent, #C9A227); color: #fff; border-radius: 6px; font-size: 0.75rem; font-weight: 600; text-decoration: none;">
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/></svg>
                    Descargar PDF
                </a>
            </div>
            <iframe src="${pdfSrc}" style="width: 100%; height: 450px; border: 1px solid var(--border); border-radius: 6px; background: #fff;"></iframe>
        </div>`;
    }

    // 2. E-14 matrix (nivelación + partidos con código + totales)
    if (detail.partidos && detail.partidos.length > 0) {
        const confPct = ((detail.overall_confidence || 0) * 100).toFixed(0);
        const confColor = confPct >= OCR_LEGIBILITY ? '#2D7A3E' : '#B07D10';
        html += `<div style="margin-bottom: 1rem;">
            <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 0.5rem;">
                <h4 style="margin: 0; color: var(--text); font-size: 0.9rem;">Matriz E-14 (Extraída por OCR)</h4>
                <span style="font-size: 0.75rem; color: ${confColor}; font-weight: 600;">Legibilidad OCR: ${confPct}%</span>
            </div>
            ${renderE14Matrix(detail)}
        </div>`;
    }

    // 3. Raw OCR text removed per design decision

    if (html) {
        container.innerHTML = html;
        return;
    }

    // Fallback: image/PDF
    const imageUrl = detail.image_url || detail.form_image_url;
    const pdfUrl = detail.pdf_url || detail.pdfUrl;

    if (imageUrl) {
        container.innerHTML = `<img src="${imageUrl}" alt="Formulario E-14" style="max-width: 100%; height: auto; border-radius: 6px;">`;
    } else if (pdfUrl) {
        container.innerHTML = `<div style="display: flex; flex-direction: column; gap: 0.75rem;">
            <a class="incident-action-btn" href="${pdfUrl}" target="_blank" rel="noopener">Abrir PDF E-14</a>
            <iframe src="${pdfUrl}" style="width: 100%; height: 420px; border: 1px solid var(--border); border-radius: 6px;"></iframe>
        </div>`;
    } else {
        container.textContent = 'Evidencia E-14 no disponible para esta mesa.';
    }
}

function renderOcrFields(fields) {
    const container = document.getElementById('mesa-ocr-fields');
    if (!container || !fields || !fields.length) return;

    container.innerHTML = fields.map(field => {
        const confPct = (field.confidence * 100).toFixed(0);
        const confClass = confidenceClass(field.confidence * 100);
        const reviewClass = field.needs_review ? 'needs-review' : '';

        return `
            <div class="ocr-field-row ${reviewClass}">
                <span class="ocr-field-label">${field.label}</span>
                <div class="ocr-field-value">
                    <span class="ocr-field-number">${formatNumber(field.value)}</span>
                    <span class="ocr-field-confidence ${confClass}">${confPct}%</span>
                </div>
            </div>
        `;
    }).join('');
}

function renderValidations(validations) {
    const container = document.getElementById('mesa-validations');

    container.innerHTML = validations.map(v => {
        const rule = v.check || v.rule || '';

        if (rule === 'HITL-01') {
            const priority = v.review_priority || 'MEDIUM';
            const color = priority === 'CRITICAL' ? '#c0392b' : priority === 'HIGH' ? '#e67e22' : '#b7600a';
            return `
                <div class="validation-row failed" style="background:${color}18; border-left: 3px solid ${color}; padding: 0.5rem 0.75rem; border-radius:4px;">
                    <span class="validation-icon" style="color:${color};">👤</span>
                    <span class="validation-name" style="color:${color}; font-weight:700;">HITL · Revisión Humana</span>
                    <span class="validation-message" style="color:${color};">${v.message || v.detail || ''}</span>
                </div>
            `;
        }

        const passedClass = v.passed ? 'passed' : 'failed';
        const icon = v.passed ? '✓' : '✗';

        return `
            <div class="validation-row ${passedClass}">
                <span class="validation-icon">${icon}</span>
                <span class="validation-name">${rule}</span>
                <span class="validation-message">${v.detail || v.message || ''}</span>
            </div>
        `;
    }).join('');
}

function renderMesaIncidents(incidents) {
    const container = document.getElementById('mesa-incidents-list');

    if (!incidents || incidents.length === 0) {
        container.innerHTML = '<div style="color: var(--success); font-size: 0.8rem;">✓ Sin incidentes activos</div>';
        return;
    }

    container.innerHTML = incidents.map(inc => `
        <div class="mesa-incident-item">
            <span class="severity-badge ${inc.severity.toLowerCase()}">${inc.severity}</span>
            <span class="incident-type">${inc.type}</span>
            <span class="mesa-incident-desc">${inc.description}</span>
        </div>
    `).join('');
}

/**
 * Renders juridical observations for a mesa.
 * First checks pre-loaded litigio incidencias, then derives from form data.
 * @param {Object} detail - Mesa detail object from renderMesaDetail
 */
function renderMesaOcrEvidence(detail) {
    const container = document.getElementById('mesa-ocr-evidence');
    if (!container) return;

    const fields = detail.ocr_fields || [];
    const partidos = detail.partidos || [];
    const header = detail.header || {};
    const confPct = (detail.overall_confidence * 100).toFixed(1);
    const warnings = detail.warnings || [];

    const locParts = [
        header.departamento || '', header.municipio || '',
        header.puesto || '',
        header.zona ? `Z${String(header.zona).padStart(2, '0')}` : '',
        header.mesa_number ? `M${header.mesa_number}` : ''
    ].filter(Boolean);

    const totalVotos = fields.find(f => f.label === 'Total Votos')?.value || 0;
    const vBlancos = fields.find(f => f.label === 'Votos Blancos')?.value || 0;
    const vNulos = fields.find(f => f.label === 'Votos Nulos')?.value || 0;
    const partySum = fields.find(f => f.label === 'Suma Partidos')?.value || 0;

    const warningsHtml = warnings.length > 0
        ? warnings.map(w => `<li style="font-size: 0.75rem;">${escapeHtml(w)}</li>`).join('')
        : '<li style="font-size: 0.75rem; color: var(--muted);">Ninguna</li>';

    container.innerHTML = `
        <table style="width: 100%; font-size: 0.8rem; border-collapse: collapse;">
            <tr style="border-bottom: 1px solid var(--border);"><td style="padding: 0.3rem; color: var(--muted);">Ubicacion</td><td style="padding: 0.3rem; font-weight: 600; color: var(--text);">${escapeHtml(locParts.join(' > '))}</td></tr>
            <tr style="border-bottom: 1px solid var(--border);"><td style="padding: 0.3rem; color: var(--muted);">Corporacion</td><td style="padding: 0.3rem; color: var(--text);">${escapeHtml(header.corporacion || '')}</td></tr>
            <tr style="border-bottom: 1px solid var(--border);"><td style="padding: 0.3rem; color: var(--muted);">Legibilidad OCR</td><td style="padding: 0.3rem; color: ${parseFloat(confPct) >= 75 ? 'var(--success)' : 'var(--warning)'}; font-weight: 600;">${confPct}%</td></tr>
            <tr style="border-bottom: 1px solid var(--border);"><td style="padding: 0.3rem; color: var(--muted);">Total Votos</td><td style="padding: 0.3rem; color: var(--text);">${totalVotos.toLocaleString()}</td></tr>
            <tr style="border-bottom: 1px solid var(--border);"><td style="padding: 0.3rem; color: var(--muted);">Votos Blancos</td><td style="padding: 0.3rem; color: var(--text);">${vBlancos.toLocaleString()}</td></tr>
            <tr style="border-bottom: 1px solid var(--border);"><td style="padding: 0.3rem; color: var(--muted);">Votos Nulos</td><td style="padding: 0.3rem; color: var(--text);">${vNulos.toLocaleString()}</td></tr>
            <tr style="border-bottom: 1px solid var(--border);"><td style="padding: 0.3rem; color: var(--muted);">Suma Partidos</td><td style="padding: 0.3rem; color: var(--text);">${partySum.toLocaleString()}</td></tr>
            <tr style="border-bottom: 1px solid var(--border);"><td style="padding: 0.3rem; color: var(--muted);">Partidos Detectados</td><td style="padding: 0.3rem; color: var(--text);">${partidos.length}</td></tr>
            <tr><td style="padding: 0.3rem; color: var(--muted); vertical-align: top;">Advertencias</td><td style="padding: 0.3rem;"><ul style="margin: 0; padding-left: 1rem; color: var(--text);">${warningsHtml}</ul></td></tr>
        </table>`;
}

function renderMesaTraceability(detail) {
    const srcEl = document.getElementById('mesa-trace-source');
    const dateEl = document.getElementById('mesa-trace-date');
    const confEl = document.getElementById('mesa-trace-confidence');
    if (!srcEl) return;

    srcEl.textContent = 'RNEC / OCR Tesseract CASTOR';
    dateEl.textContent = new Date().toLocaleString();
    confEl.textContent = detail.overall_confidence
        ? `${(detail.overall_confidence * 100).toFixed(1)}%`
        : 'N/A';
}

function renderMesaJuridicalObs(detail) {
    const container = document.getElementById('mesa-juridical-obs');
    if (!container) return;

    const mesaId = detail.mesa_id;
    const formId = detail.form_id;

    // Try pre-loaded litigio incidencias first
    let incidents = (window._litigioIncidencias || []).filter(i =>
        (mesaId && (i.mesa == mesaId || String(i.mesa) === String(mesaId)))
        || (formId && (i.form_id == formId || String(i.form_id) === String(formId)))
    );

    // If litigio tab hasn't loaded yet, derive observations from form data
    if (incidents.length === 0) {
        incidents = deriveJuridicalObs(detail);
    }

    if (incidents.length === 0) {
        container.innerHTML = '<div style="color: var(--muted); font-size: 0.8rem;">Sin observaciones juridicas</div>';
        return;
    }

    container.innerHTML = incidents.map(inc => {
        const prioColor = inc.prioridad === 'alta' ? 'var(--danger, #DC2626)' : 'var(--warning, #F59E0B)';
        return `<div style="padding:0.6rem;margin-bottom:0.5rem;background:rgba(139,115,85,0.05);border-left:3px solid ${prioColor};border-radius:4px;">
            <p style="margin:0 0 0.2rem;font-size:0.75rem;color:var(--muted);">${escapeHtml(inc.rj_id || '')} — ${escapeHtml(inc.rj_nombre || '')}</p>
            <p style="margin:0 0 0.3rem;"><strong>Incidencia:</strong> ${escapeHtml(inc.incidencia || '')}</p>
            <p style="margin:0 0 0.3rem;"><strong>Fundamento Legal:</strong> ${escapeHtml(inc.fundamento || inc.cpaca_fundamento || '')}</p>
            <p style="margin:0 0 0.3rem;font-size:0.78rem;color:#555;">${escapeHtml(inc.descripcion_juridica || '')}</p>
            <p style="margin:0 0 0.2rem;"><strong>Irregularidad:</strong> ${escapeHtml(inc.tipo_irregularidad || '')}
              &nbsp;·&nbsp; <strong>Gravedad:</strong> <span style="color:${prioColor};font-weight:700;">${escapeHtml(inc.nivel_gravedad || (inc.prioridad || '').toUpperCase())}</span></p>
            <p style="margin:0 0 0.2rem;"><strong>Votos Afectados:</strong> ${(inc.votos || 0).toLocaleString()} &nbsp;·&nbsp;
              <strong>Viabilidad:</strong> ${inc.viabilidad || 0}%</p>
            ${inc.observaciones ? `<p style="margin:0 0 0.2rem;font-size:0.76rem;"><strong>Advertencias OCR:</strong> ${escapeHtml(inc.observaciones)}</p>` : ''}
        </div>`;
    }).join('');
}

// ── Reglas jurídicas electorales RJ-01…RJ-06 ─────────────────────────────
const REGLAS_JURIDICAS = {
    'RJ-01': {
        id: 'RJ-01', nombre: 'Exceso de sufragantes',
        articulos: [{ norma: 'Código Electoral', articulo: 192, numeral: 5 }],
        descripcion: 'Se configura cuando el número de sufragantes registrados en una mesa excede el número de ciudadanos habilitados para votar en ella.',
        tipo: 'Exceso de votos respecto a censo habilitado',
        gravedad: 'Alta',
        verificable: ['Formulario E-11', 'Formulario E-14', 'Listado de ciudadanos habilitados'],
    },
    'RJ-02': {
        id: 'RJ-02', nombre: 'Diferencia superior al 10% entre Senado y Cámara en la misma mesa',
        articulos: [{ norma: 'Código Electoral', articulo: 164 }],
        descripcion: 'Se configura cuando existe una diferencia superior al 10% entre el total de votos depositados para Senado y Cámara en la misma mesa.',
        tipo: 'Desproporción electoral entre corporaciones',
        gravedad: 'Alta',
        verificable: ['Formulario E-14 Senado', 'Formulario E-14 Cámara'],
    },
    'RJ-03': {
        id: 'RJ-03', nombre: 'Error aritmético o discordancia entre formularios',
        articulos: [{ norma: 'Código Electoral', articulo: 192, numeral: 11 }],
        descripcion: 'Se configura cuando existe error en la sumatoria de votos o discordancia entre documentos electorales que afecte la fidelidad del escrutinio.',
        tipo: 'Error de sumatoria o transcripción',
        gravedad: 'Alta',
        verificable: ['Formulario E-14', 'Formulario E-24', 'Formulario E-11'],
    },
    'RJ-04': {
        id: 'RJ-04', nombre: 'Destrucción o pérdida de votos y ausencia del acta',
        articulos: [{ norma: 'Código Electoral', articulo: 192, numeral: 4 }],
        descripcion: 'Se configura cuando se hayan destruido o perdido los votos emitidos y no exista acta de escrutinio válida que permita determinar el resultado.',
        tipo: 'Imposibilidad de verificar resultado electoral',
        gravedad: 'Crítica',
        verificable: ['Acta de escrutinio', 'Material electoral', 'Registro de urna'],
    },
    'RJ-05': {
        id: 'RJ-05', nombre: 'Tachones, enmendaduras o alteraciones en documentos electorales',
        articulos: [
            { norma: 'Código Electoral', articulo: 163 },
            { norma: 'Ley 62 de 1988', articulo: 11 },
        ],
        descripcion: 'Se configura cuando los formularios electorales presentan tachones, enmendaduras o alteraciones materiales que afecten su autenticidad.',
        tipo: 'Alteración física del documento electoral',
        gravedad: 'Media-Alta',
        verificable: ['Revisión física del E-14', 'Comparación de ejemplares', 'Análisis pericial documental'],
    },
    'RJ-06': {
        id: 'RJ-06', nombre: 'Falta de firmas en acta de escrutinio',
        articulos: [{ norma: 'Código Electoral', articulo: 192, numeral: 3 }],
        descripcion: 'Se configura cuando el acta de escrutinio de jurados está firmada por menos de tres jurados de votación.',
        tipo: 'Falta de requisito esencial de validez',
        gravedad: 'Alta',
        verificable: ['Acta E-14 original', 'Revisión material del documento'],
    },
};

const PMSN_TO_RJ = {
    'PMSN-01': ['RJ-02'],
    'PMSN-02': ['RJ-05'],
    'PMSN-03': ['RJ-03'],
    'PMSN-04': ['RJ-01', 'RJ-03'],
    'PMSN-05': ['RJ-02'],
    'PMSN-06': ['RJ-06'],
    'PMSN-07': ['RJ-03'],
};

function _rjLabel(rjId) {
    const r = REGLAS_JURIDICAS[rjId];
    if (!r) return rjId;
    const arts = r.articulos.map(a =>
        `Art. ${a.articulo}${a.numeral ? ` num. ${a.numeral}` : ''} ${a.norma}`
    ).join(' / ');
    return `${rjId} — ${r.nombre} (${arts})`;
}

function _buildObs(rjId, incidencia, votos, warnings) {
    const r = REGLAS_JURIDICAS[rjId] || {};
    const arts = (r.articulos || []).map(a =>
        `Art. ${a.articulo}${a.numeral ? ` num. ${a.numeral}` : ''} ${a.norma}`
    ).join(' / ');
    const grav = r.gravedad || '';
    return {
        rj_id: rjId,
        rj_nombre: r.nombre || rjId,
        incidencia,
        fundamento: arts,
        descripcion_juridica: r.descripcion || '',
        tipo_irregularidad: r.tipo || '',
        nivel_gravedad: grav,
        articulos: r.articulos || [],
        prioridad: grav.toLowerCase().includes('alta') || grav.includes('rít') ? 'alta' : 'media',
        viabilidad: grav === 'Crítica' ? 95 : grav === 'Alta' ? 85 : 65,
        votos,
        observaciones: warnings.join('; '),
    };
}

/**
 * Derives juridical observations from mesa detail data (validations + confidence).
 * Maps PMSN rules and OCR confidence to RJ-01…RJ-06 (Código Electoral).
 * @param {Object} detail
 * @returns {Array} Array of observation objects
 */
function deriveJuridicalObs(detail) {
    const obs = [];
    const confPct = (detail.overall_confidence || 0) * 100;
    const validations = detail.validations || [];
    const totalVotos = detail.ocr_fields?.find(f => f.label === 'Total Votos')?.value || 0;
    const partySum = detail.ocr_fields?.find(f => f.label === 'Suma Partidos')?.value || 0;
    const blancos = detail.ocr_fields?.find(f => f.label === 'Votos Blancos')?.value || 0;
    const nulos = detail.ocr_fields?.find(f => f.label === 'Votos Nulos')?.value || 0;
    const fullSum = detail.ocr_fields?.find(f => f.label?.startsWith('Suma Total'))?.value
        ?? (partySum + blancos + nulos);
    const noMarcados = fullSum - partySum - blancos - nulos;
    const warnings = detail.warnings || [];

    // Check for arithmetic error
    const arithFail = validations.find(v => v.check && v.check.includes('Suma') && !v.passed);
    if (arithFail) {
        obs.push(_buildObs(
            'RJ-03',
            `Error aritmético: (partidos=${partySum} + blancos=${blancos} + nulos=${nulos} + no_marcados=${noMarcados})=${fullSum} ≠ total=${totalVotos} (dif: ${Math.abs(fullSum - totalVotos)})`,
            totalVotos,
            warnings
        ));
    }

    // Check for low OCR confidence (high risk)
    if (confPct < OCR_HIGH_RISK) {
        obs.push(_buildObs(
            'RJ-05',
            `Confianza OCR muy baja: ${confPct.toFixed(1)}% — documento posiblemente ilegible o alterado`,
            totalVotos,
            warnings
        ));
    } else if (confPct < OCR_MEDIUM_RISK && !arithFail) {
        obs.push(_buildObs(
            'RJ-05',
            `Confianza OCR intermedia: ${confPct.toFixed(1)}% — requiere verificación física del acta`,
            totalVotos,
            warnings
        ));
    }

    // Check for PMSN rule alerts from the incidents table
    const mesaIncidents = (allIncidents || []).filter(
        i => String(i.mesa_id) === String(detail.mesa_id)
    );
    if (mesaIncidents.length > 0) {
        const allRules = mesaIncidents.flatMap(i =>
            (i.rules && i.rules.length)
                ? i.rules
                : [{ rule_id: i.rule_id || i.incident_type || '—', risk_type: i.risk_type, description: i.description || 'Anomalia PMSN' }]
        );
        const seenRuleIds = new Set();
        const uniqueRules = allRules.filter(r => {
            if (seenRuleIds.has(r.rule_id)) return false;
            seenRuleIds.add(r.rule_id);
            return true;
        });
        for (const rule of uniqueRules) {
            const rjIds = PMSN_TO_RJ[rule.rule_id] || ['RJ-03'];
            for (const rjId of rjIds) {
                obs.push(_buildObs(
                    rjId,
                    `Anomalía PMSN: ${rule.rule_id} — ${rule.description}`,
                    totalVotos,
                    warnings
                ));
            }
        }
    }

    return obs;
}

// Mesa Detail Actions
window.createMesaIncident = function() {
    if (!currentMesaDetail) return;

    const incidentType = prompt('Tipo de incidente:\n1. OCR_LOW_CONF\n2. ARITHMETIC_FAIL\n3. DISCREPANCY_RNEC\n4. SOURCE_MISMATCH\n\nIngrese número o nombre:');
    if (!incidentType) return;

    const typeMap = { '1': 'OCR_LOW_CONF', '2': 'ARITHMETIC_FAIL', '3': 'DISCREPANCY_RNEC', '4': 'SOURCE_MISMATCH' };
    const finalType = typeMap[incidentType] || incidentType.toUpperCase();

    const description = prompt('Descripción del incidente:');
    if (!description) return;

    // Create incident via API
    fetch('/api/incidents', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            incident_type: finalType,
            mesa_id: currentMesaDetail.mesa_id,
            dept_code: currentMesaDetail.header.dept_code,
            dept_name: currentMesaDetail.header.dept_name,
            muni_name: currentMesaDetail.header.muni_name,
            puesto: currentMesaDetail.header.puesto,
            description: description,
            ocr_confidence: currentMesaDetail.overall_confidence
        })
    })
    .then(res => res.json())
    .then(data => {
        if (data.success) {
            alert('Incidente creado exitosamente');
            loadIncidents(); // Refresh incident queue
            openMesaDetail(currentMesaDetail.mesa_id); // Refresh mesa detail
        } else {
            alert('Error: ' + data.error);
        }
    })
    .catch(err => {
        console.error('Error creating incident:', err);
        alert('Error de conexión');
    });
};

window.callWitnessForMesa = function() {
    if (!currentMesaDetail) return;

    // Close mesa modal and switch to witness tab
    closeMesaDetailModal();

    // Switch to witness tab
    document.querySelector('[data-tab="llamar-testigo"]').click();

    alert(`Seleccione un testigo para enviar a:\n${currentMesaDetail.header.puesto}\nMesa ${currentMesaDetail.mesa_id}`);
};

window.markMesaResolved = function() {
    if (!currentMesaDetail) return;

    if (confirm(`¿Marcar mesa ${currentMesaDetail.mesa_id} como resuelta?`)) {
        alert('Mesa marcada como resuelta');
        closeMesaDetailModal();
        loadIncidents(); // Refresh
    }
};

// Make openMesaDetail available globally
window.openMesaDetail = openMesaDetail;

// ============================================================
// MAP FILTERS
// ============================================================


function populateSelect(id, options) {
    const select = document.getElementById(id);
    if (!select) return;

    // Keep first option (Todos/Todas)
    const firstOption = select.options[0];
    select.innerHTML = '';
    select.appendChild(firstOption);

    options.forEach(opt => {
        const option = document.createElement('option');
        option.value = opt;
        option.textContent = opt;
        select.appendChild(option);
    });
}





function updateMapFilter(key, value) {
    if (!window.mapFilters) window.mapFilters = {};
    window.mapFilters[key] = value;
}





// Make map filter functions globally available
window.filterMapByDept = filterMapByDept;
window.filterMapByMuni = filterMapByMuni;
window.filterMapByZona = filterMapByZona;
window.filterMapByPuesto = filterMapByPuesto;
window.clearMapFilters = clearMapFilters;

// ============================================================
// INCIDENT ACTIONS
// ============================================================

// Estado para el modal de enviar testigo
let currentIncidentForAssignment = null;
let witnessesForAssignment = [];

function enviarTestigoARevision(incidentId, mesaId) {
    // Find the incident details
    const incident = allIncidents.find(i => i.id === incidentId);
    if (!incident) {
        alert('Incidente no encontrado');
        return;
    }

    currentIncidentForAssignment = incident;

    // Buscar testigos que cubren la zona del incidente
    witnessesForAssignment = allWitnesses.filter(w => {
        // Solo testigos disponibles
        if (w.status !== 'available') return false;

        // Filtrar por zona de cobertura
        if (w.coverage_dept_name && incident.dept_name) {
            if (w.coverage_dept_name !== incident.dept_name) return false;

            // Si tiene municipio, verificar
            if (w.coverage_muni_name && incident.muni_name) {
                if (w.coverage_muni_name !== incident.muni_name) return false;
            }
        }
        return true;
    });

    // Si no hay testigos con cobertura, mostrar todos los disponibles
    if (witnessesForAssignment.length === 0) {
        witnessesForAssignment = allWitnesses.filter(w => w.status === 'available');
    }

    if (witnessesForAssignment.length === 0) {
        alert(`No hay testigos disponibles.\n\nGenere un QR de registro para agregar testigos.`);
        return;
    }

    // Mostrar modal de selección
    openAssignWitnessModal(incident, witnessesForAssignment);
}

function openAssignWitnessModal(incident, witnesses) {
    // Crear modal dinámicamente si no existe
    let modal = document.getElementById('assign-witness-modal');
    if (!modal) {
        modal = document.createElement('div');
        modal.id = 'assign-witness-modal';
        modal.className = 'modal-overlay';
        modal.innerHTML = `
            <div class="modal" style="max-width: 600px;">
                <div class="modal-header">
                    <h3 class="modal-title">Enviar Testigo a Mesa</h3>
                    <button class="modal-close" onclick="closeAssignWitnessModal()">&times;</button>
                </div>
                <div class="modal-body">
                    <div id="assign-witness-incident-info" style="background: var(--panel); padding: 1rem; border-radius: 8px; margin-bottom: 1rem;"></div>
                    <h4 style="margin-bottom: 0.5rem;">Testigos Disponibles en la Zona</h4>
                    <p style="color: var(--muted); font-size: 0.8rem; margin-bottom: 1rem;">Seleccione un testigo para enviar a revisar esta mesa</p>
                    <div id="assign-witness-list" style="max-height: 300px; overflow-y: auto;"></div>
                </div>
            </div>
        `;
        document.body.appendChild(modal);
    }

    // Llenar info del incidente
    document.getElementById('assign-witness-incident-info').innerHTML = `
        <p style="margin: 0 0 0.5rem;"><strong>Mesa:</strong> ${escapeHtml(incident.mesa_id)}</p>
        <p style="margin: 0 0 0.5rem;"><strong>Ubicación:</strong> ${escapeHtml(incident.dept_name || '')} > ${escapeHtml(incident.muni_name || '')} > ${escapeHtml(incident.puesto_name || '')}</p>
        <p style="margin: 0 0 0.5rem;"><strong>Incidente:</strong> <span class="severity-badge ${incident.severity?.toLowerCase()}">${incident.severity}</span> ${escapeHtml(incident.type_label || incident.type)}</p>
        <p style="margin: 0;"><strong>Descripción:</strong> ${escapeHtml(incident.description || 'Sin descripción')}</p>
    `;

    // Llenar lista de testigos
    const listContainer = document.getElementById('assign-witness-list');
    listContainer.innerHTML = witnesses.map(w => `
        <div class="witness-select-card" style="background: var(--bg); padding: 1rem; border-radius: 8px; margin-bottom: 0.5rem; display: flex; justify-content: space-between; align-items: center; border: 1px solid var(--border);">
            <div>
                <div style="font-weight: 600;">${escapeHtml(w.name)}</div>
                <div style="font-size: 0.85rem; color: var(--muted);">
                    <span style="margin-right: 1rem;">Tel: ${escapeHtml(w.phone)}</span>
                    ${w.push_enabled ? '<span style="color: var(--success);">Push activo</span>' : '<span style="color: var(--warning);">Sin push</span>'}
                </div>
                <div style="font-size: 0.8rem; color: var(--muted);">
                    Cubre: ${escapeHtml(w.coverageDisplay || 'Sin zona asignada')}
                </div>
            </div>
            <button class="btn-action primary" onclick="confirmAssignWitness(${w.id}, ${w.push_enabled})">
                ${w.push_enabled ? 'Notificar' : 'Asignar'}
            </button>
        </div>
    `).join('');

    if (witnesses.length === 0) {
        listContainer.innerHTML = '<div class="empty-state"><p>No hay testigos disponibles</p></div>';
    }

    modal.classList.add('active');
}

function closeAssignWitnessModal() {
    const modal = document.getElementById('assign-witness-modal');
    if (modal) {
        modal.classList.remove('active');
    }
    currentIncidentForAssignment = null;
    witnessesForAssignment = [];
}

async function confirmAssignWitness(witnessId, hasPush) {
    const witness = witnessesForAssignment.find(w => w.id === witnessId);
    const incident = currentIncidentForAssignment;

    if (!witness || !incident) {
        alert('Error: datos incompletos');
        return;
    }

    const action = hasPush ? 'notificar' : 'asignar';
    if (!confirm(`¿${hasPush ? 'Enviar notificación a' : 'Asignar a'} ${witness.name} para revisar mesa ${incident.mesa_id}?`)) {
        return;
    }

    try {
        // 1. Crear asignación via API
        const assignResponse = await fetch(`${WITNESS_API}/assignments`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                witness_id: witnessId,
                polling_table_id: parseInt(incident.mesa_id.replace(/\D/g, '')) || 1,
                contest_id: 1,
                priority: incident.severity === 'CRITICAL' ? 10 : (incident.severity === 'HIGH' ? 7 : 5),
                reason: `Incidente #${incident.id}: ${incident.type_label || incident.type} - ${incident.description || ''}`,
                send_notification: hasPush
            })
        });

        const assignData = await assignResponse.json();

        if (!assignResponse.ok) {
            throw new Error(assignData.error || 'Error creando asignación');
        }

        // 2. Actualizar estado del incidente localmente
        incident.status = 'ASSIGNED';
        incident.assigned_to = witness.name;
        incident.assigned_at = new Date().toISOString();

        // 3. Actualizar estado del testigo localmente
        witness.status = 'busy';

        // 4. Mostrar confirmación
        const pushMsg = hasPush ? '\nSe envió notificación push al testigo.' : '\nEl testigo NO tiene push activo - contactarlo manualmente.';
        alert(`Testigo ${witness.name} asignado a mesa ${incident.mesa_id}.${pushMsg}\n\nTeléfono: ${witness.phone}`);

        // 5. Cerrar modal y refrescar tabla
        closeAssignWitnessModal();
        renderIncidentTable();

        console.log(`Asignación creada: Testigo ${witnessId} -> Incidente ${incident.id}`);

    } catch (error) {
        console.error('Error en asignación:', error);
        alert('Error: ' + error.message);
    }
}

// Legacy function - redirect to new flow
function enviarTestigoARevisionLegacy(incidentId, mesaId) {
    // Find the incident details
    const incident = allIncidents.find(i => i.id === incidentId);
    if (!incident) {
        alert('Incidente no encontrado');
        return;
    }

    // Find available witnesses for this location
    const availableWitnesses = allWitnesses.filter(w =>
        w.status === 'available' &&
        (w.coverage_dept_name === incident.dept_name || !w.coverage_dept_name)
    );

    if (availableWitnesses.length === 0) {
        alert(`No hay testigos disponibles para la zona de ${incident.dept_name || mesaId}`);
        return;
    }

    // Show witness selection modal
    const witnessOptions = availableWitnesses.map(w =>
        `${w.name} (${w.phone || 'Sin teléfono'})`
    ).join('\n');

    const selectedIndex = prompt(
        `Seleccione un testigo para enviar a mesa ${mesaId}:\n\n` +
        availableWitnesses.map((w, i) => `${i + 1}. ${w.name}`).join('\n') +
        `\n\nIngrese el número (1-${availableWitnesses.length}):`
    );

    if (!selectedIndex) return;

    const idx = parseInt(selectedIndex) - 1;
    if (idx < 0 || idx >= availableWitnesses.length) {
        alert('Selección inválida');
        return;
    }

    const selectedWitness = availableWitnesses[idx];

    // Confirm and send
    if (confirm(`¿Enviar a ${selectedWitness.name} a revisar mesa ${mesaId}?`)) {
        // Update incident status
        incident.status = 'ASSIGNED';
        incident.assigned_to = selectedWitness.name;
        incident.assigned_at = new Date().toISOString();

        // Update witness status
        selectedWitness.status = 'ASSIGNED';
        selectedWitness.assigned_mesa = mesaId;

        // Log the action
        console.log(`Testigo ${selectedWitness.name} asignado a mesa ${mesaId} para incidente ${incidentId}`);

        alert(`✅ Testigo ${selectedWitness.name} enviado a revisar mesa ${mesaId}`);

        // Refresh the incident table
        renderIncidentTable();
    }
}

// Make incident action globally available
window.enviarTestigoARevision = enviarTestigoARevision;
window.closeAssignWitnessModal = closeAssignWitnessModal;
window.confirmAssignWitness = confirmAssignWitness;

// ============================================================
// IMMEDIATE INITIALIZATION - Ensure candidates render
// ============================================================
(function initCandidatesNow() {
    // If DOM is already loaded, render immediately
    if (document.readyState === 'complete' || document.readyState === 'interactive') {
        setTimeout(() => {
            console.log('Immediate candidate render triggered');
            renderTrackedCandidates();
        }, 500);
    }
})();

// ============================================================
// WITNESS API INTEGRATION
// ============================================================

const WITNESS_API = '/api/witness';
let currentQRData = null;

/**
 * Load witnesses from API
 */
async function loadWitnessesFromAPI() {
    try {
        const response = await fetch(`${WITNESS_API}/list`);
        const data = await response.json();

        if (data.success) {
            // Update allWitnesses with real data including coverage
            allWitnesses = data.witnesses.map(w => ({
                id: w.id,
                name: w.full_name,
                phone: w.phone,
                currentLocation: w.current_zone || 'Sin ubicacion',
                status: w.status === 'ACTIVE' ? 'available' : 'busy',
                distance: '0.0',
                push_enabled: w.push_enabled,
                lat: w.current_lat,
                lon: w.current_lon,
                // Zona de cobertura
                coverage_dept_code: w.coverage_dept_code,
                coverage_dept_name: w.coverage_dept_name,
                coverage_muni_code: w.coverage_muni_code,
                coverage_muni_name: w.coverage_muni_name,
                coverage_station_name: w.coverage_station_name,
                // Para mostrar en UI
                coverageDisplay: formatCoverage(w)
            }));

            // Update stats summary
            const statsEl = document.getElementById('witness-stats-summary');
            if (statsEl) {
                statsEl.textContent = `${data.total} testigos registrados | ${data.push_enabled_count} con push activo`;
            }

            console.log(`Loaded ${data.total} witnesses from API`);
        }
    } catch (error) {
        console.error('Error loading witnesses from API:', error);
        // No fallback data to avoid mock values
    }
}

/**
 * Formatea la zona de cobertura para mostrar
 */
function formatCoverage(witness) {
    const parts = [];
    if (witness.coverage_dept_name) parts.push(witness.coverage_dept_name);
    if (witness.coverage_muni_name) parts.push(witness.coverage_muni_name);
    if (witness.coverage_station_name) parts.push(witness.coverage_station_name);
    return parts.length > 0 ? parts.join(' > ') : 'Sin zona asignada';
}

/**
 * Filtra testigos por zona de cobertura
 */
async function loadWitnessesByCoverage(deptCode, muniCode = null, stationName = null) {
    try {
        let url = `${WITNESS_API}/by-coverage?dept_code=${deptCode}`;
        if (muniCode) url += `&muni_code=${muniCode}`;
        if (stationName) url += `&station_name=${encodeURIComponent(stationName)}`;

        const response = await fetch(url);
        const data = await response.json();

        if (data.success) {
            return data.witnesses.map(w => ({
                id: w.id,
                name: w.full_name,
                phone: w.phone,
                status: w.status === 'ACTIVE' ? 'available' : 'busy',
                push_enabled: w.push_enabled,
                coverageDisplay: formatCoverage(w)
            }));
        }
        return [];
    } catch (error) {
        console.error('Error loading witnesses by coverage:', error);
        return [];
    }
}

/**
 * Load witness stats
 */
async function loadWitnessStats() {
    try {
        const response = await fetch(`${WITNESS_API}/stats`);
        const data = await response.json();

        if (data.success) {
            const statsEl = document.getElementById('witness-stats-summary');
            if (statsEl) {
                statsEl.textContent = `${data.stats.total_registered} testigos | ${data.stats.push_enabled} con push | ${data.stats.active} activos`;
            }
        }
    } catch (error) {
        console.error('Error loading witness stats:', error);
    }
}

// ============================================================
// WITNESS REGISTRATION FORM
// ============================================================

function toggleRegisterForm() {
    const form = document.getElementById('register-witness-form');
    if (!form) return;

    const isVisible = form.style.display !== 'none';
    form.style.display = isVisible ? 'none' : 'block';

    // Populate departments if showing
    if (!isVisible) {
        populateWitnessDepartments();
    }
}

// Department codes mapping
const DEPT_CODES = {
    'Antioquia': '05', 'Atlántico': '08', 'Bogotá D.C.': '11', 'Bolívar': '13',
    'Boyacá': '15', 'Caldas': '17', 'Caquetá': '18', 'Cauca': '19', 'Cesar': '20',
    'Córdoba': '23', 'Cundinamarca': '25', 'Chocó': '27', 'Huila': '41',
    'La Guajira': '44', 'Magdalena': '47', 'Meta': '50', 'Nariño': '52',
    'Norte de Santander': '54', 'Quindío': '63', 'Risaralda': '66', 'Santander': '68',
    'Sucre': '70', 'Tolima': '73', 'Valle del Cauca': '76'
};

const DEPT_CODE_TO_NAME = Object.keys(DEPT_CODES).reduce((acc, name) => {
    acc[DEPT_CODES[name]] = name;
    return acc;
}, {});

const DEPT_ABBR_TO_NAME = {
    'AN': 'Antioquia',
    'AT': 'Atlántico',
    'BO': 'Bogotá D.C.',
    'BL': 'Bolívar',
    'BY': 'Boyacá',
    'CA': 'Caldas',
    'CQ': 'Caquetá',
    'CU': 'Cauca',
    'CE': 'Cesar',
    'CO': 'Córdoba',
    'CM': 'Cundinamarca',
    'CH': 'Chocó',
    'HU': 'Huila',
    'LG': 'La Guajira',
    'MA': 'Magdalena',
    'ME': 'Meta',
    'NA': 'Nariño',
    'NS': 'Norte de Santander',
    'QN': 'Quindío',
    'RI': 'Risaralda',
    'SA': 'Santander',
    'SU': 'Sucre',
    'TO': 'Tolima',
    'VA': 'Valle del Cauca'
};

const DEPT_ABBR_TO_CODE = Object.keys(DEPT_ABBR_TO_NAME).reduce((acc, abbr) => {
    const name = DEPT_ABBR_TO_NAME[abbr];
    const code = DEPT_CODES[name];
    if (code) acc[abbr] = code;
    return acc;
}, {});

let E14_GEO_LOOKUP = {
    deptByCode: {},
    muniByCode: {}
};
let MUNI_CATALOG = {};
let DEPT_CODE_TO_NAME_RNEC = {};
let PUESTO_CATALOG = {};
let muniCatalogLoaded = false;

function populateWitnessDepartments() {
    const deptSelect = document.getElementById('witness-dept');
    if (!deptSelect) return;

    const defaultDepts = Object.keys(DEPT_CODES).sort();

    deptSelect.innerHTML = '<option value="">Seleccionar...</option>';
    defaultDepts.forEach(dept => {
        const option = document.createElement('option');
        option.value = DEPT_CODES[dept];  // Use code as value
        option.textContent = dept;
        option.dataset.name = dept;  // Store name in data attribute
        deptSelect.appendChild(option);
    });
}

async function registerWitness() {
    const name = document.getElementById('witness-name')?.value?.trim();
    const phone = document.getElementById('witness-phone')?.value?.trim();
    const email = document.getElementById('witness-email')?.value?.trim();
    const deptSelect = document.getElementById('witness-dept');
    const deptCode = deptSelect?.value || '11';
    const deptName = deptSelect?.options[deptSelect.selectedIndex]?.dataset?.name || 'Bogotá D.C.';

    // Validation
    if (!name || !phone) {
        showRegisterMessage('Por favor ingresa nombre y teléfono', 'error');
        return;
    }

    if (phone.length < 10) {
        showRegisterMessage('Teléfono debe tener al menos 10 dígitos', 'error');
        return;
    }

    showRegisterMessage('Registrando...', 'info');

    try {
        // First generate a QR code to get a valid code
        const qrResponse = await fetch(`${WITNESS_API}/qr/generate`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ max_uses: 1, expires_hours: 1 })
        });
        const qrData = await qrResponse.json();

        if (!qrData.code) {
            throw new Error('No se pudo generar código de registro');
        }

        // Now register the witness with correct field names
        const response = await fetch(`${WITNESS_API}/register`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                qr_code: qrData.code,
                full_name: name,
                phone: phone,
                email: email || null,
                coverage_dept_code: deptCode,
                coverage_dept_name: deptName
            })
        });

        const data = await response.json();

        if (data.success) {
            showRegisterMessage(`Testigo "${name}" registrado exitosamente`, 'success');
            // Clear form
            document.getElementById('witness-name').value = '';
            document.getElementById('witness-phone').value = '';
            document.getElementById('witness-email').value = '';
            document.getElementById('witness-dept').selectedIndex = 0;
            // Refresh witness list
            setTimeout(() => {
                loadWitnessesFromAPI();
                toggleRegisterForm();
            }, 1500);
        } else {
            throw new Error(data.error || 'Error al registrar');
        }
    } catch (error) {
        console.error('Register error:', error);
        showRegisterMessage(error.message || 'Error al registrar testigo', 'error');
    }
}

function showRegisterMessage(msg, type) {
    const el = document.getElementById('register-message');
    if (!el) return;
    el.textContent = msg;
    el.style.display = 'block';
    el.style.color = type === 'error' ? '#e74c3c' : type === 'info' ? '#C9A227' : '#27ae60';
    if (type === 'success') {
        setTimeout(() => { el.style.display = 'none'; }, 3000);
    }
}

// Legacy QR functions (kept for compatibility)
function openGenerateQRModal() {
    toggleRegisterForm();

    // Populate filters (reuse existing department data if available)
    populateQRFilters();
}

function closeQRModal() {
    const modal = document.getElementById('qr-modal');
    if (modal) {
        modal.classList.remove('active');
    }
    currentQRData = null;
}

function populateQRFilters() {
    const deptSelect = document.getElementById('qr-dept-filter');
    const muniSelect = document.getElementById('qr-muni-filter');

    if (!deptSelect || !muniSelect) return;

    // Get unique departments from allMesas (handle both field naming conventions)
    const depts = [...new Set(allMesas.map(m => m.departamento || m.dept).filter(Boolean))].sort();

    deptSelect.innerHTML = '<option value="">Todos los departamentos</option>';
    depts.forEach(dept => {
        const option = document.createElement('option');
        option.value = dept;
        option.textContent = dept;
        deptSelect.appendChild(option);
    });

    // Update municipalities when department changes
    deptSelect.onchange = () => {
        const selectedDept = deptSelect.value;
        const munis = [...new Set(
            allMesas
                .filter(m => !selectedDept || (m.departamento || m.dept) === selectedDept)
                .map(m => m.municipio || m.muni)
                .filter(Boolean)
        )].sort();

        muniSelect.innerHTML = '<option value="">Todos los municipios</option>';
        munis.forEach(muni => {
            const option = document.createElement('option');
            option.value = muni;
            option.textContent = muni;
            muniSelect.appendChild(option);
        });
    };
}

async function generateQRCode() {
    const deptCode = document.getElementById('qr-dept-filter').value;
    const muniCode = document.getElementById('qr-muni-filter').value;
    const maxUses = parseInt(document.getElementById('qr-max-uses').value);

    try {
        const response = await fetch(`${WITNESS_API}/qr/generate`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                dept_code: deptCode || null,
                muni_code: muniCode || null,
                max_uses: maxUses,
                expires_hours: 72
            })
        });

        const data = await response.json();

        if (!response.ok) {
            throw new Error(data.error || 'Error generando QR');
        }

        currentQRData = data;

        // Show result
        document.getElementById('qr-form-section').style.display = 'none';
        document.getElementById('qr-result-section').style.display = 'block';
        document.getElementById('qr-image').src = data.qr_url;
        document.getElementById('qr-url-display').textContent = data.registration_url;

        console.log('QR generated:', data.code);

    } catch (error) {
        alert('Error: ' + error.message);
        console.error('QR generation error:', error);
    }
}

function copyQRLink() {
    if (!currentQRData) return;

    navigator.clipboard.writeText(currentQRData.registration_url)
        .then(() => alert('Enlace copiado al portapapeles'))
        .catch(err => {
            console.error('Error copying:', err);
            // Fallback
            prompt('Copie este enlace:', currentQRData.registration_url);
        });
}

function downloadQR() {
    if (!currentQRData) return;

    const link = document.createElement('a');
    link.download = `castor-qr-testigo-${currentQRData.code.slice(0, 8)}.png`;
    link.href = currentQRData.qr_url;
    link.click();
}

function generateNewQR() {
    document.getElementById('qr-form-section').style.display = 'block';
    document.getElementById('qr-result-section').style.display = 'none';
    currentQRData = null;
}

// ============================================================
// WITNESS ASSIGNMENT VIA API
// ============================================================

async function assignWitnessToMesa(witnessId, mesaId, reason) {
    try {
        const response = await fetch(`${WITNESS_API}/assignments`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                witness_id: witnessId,
                polling_table_id: parseInt(mesaId),
                contest_id: 1,
                priority: 5,
                reason: reason || 'Asignacion desde dashboard',
                send_notification: true
            })
        });

        const data = await response.json();

        if (!response.ok) {
            throw new Error(data.error || 'Error en asignacion');
        }

        return data;
    } catch (error) {
        console.error('Assignment error:', error);
        throw error;
    }
}

async function sendPushNotification(witnessIds, title, body, type = 'ALERT') {
    try {
        const response = await fetch(`${WITNESS_API}/notify`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                witness_ids: witnessIds,
                notification_type: type,
                title: title,
                body: body
            })
        });

        const data = await response.json();
        console.log(`Notification sent to ${data.sent_count} witnesses`);
        return data;
    } catch (error) {
        console.error('Notification error:', error);
        throw error;
    }
}

// ============================================================
// NEARBY WITNESSES FROM API
// ============================================================

async function findNearbyWitnessesAPI(lat, lon, radiusKm = 5) {
    try {
        const response = await fetch(`${WITNESS_API}/nearby`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                lat: lat,
                lon: lon,
                radius_km: radiusKm,
                limit: 20
            })
        });

        const data = await response.json();
        return data.witnesses || [];
    } catch (error) {
        console.error('Nearby witnesses error:', error);
        return [];
    }
}

// Make QR functions globally available
window.openGenerateQRModal = openGenerateQRModal;
window.closeQRModal = closeQRModal;
window.generateQRCode = generateQRCode;
window.copyQRLink = copyQRLink;
window.downloadQR = downloadQR;
window.generateNewQR = generateNewQR;
window.loadWitnessesFromAPI = loadWitnessesFromAPI;
window.assignWitnessToMesa = assignWitnessToMesa;
window.sendPushNotification = sendPushNotification;

// Load witness stats on init
document.addEventListener('DOMContentLoaded', () => {
    setTimeout(loadWitnessStats, 2000);
});

// ==================== IMPUGNAR MODAL ====================

let _impugnarMesaId = null;
let _impugnarIncidentId = null;
let _impugnarFormId = null;
let _impugnarMesaData = null;
let _impugnarIncidentData = null;
let _impugnarDocHtml = '';

window.openImpugnarModal = async function(mesaId, incidentId, formId = null) {
    _impugnarMesaId = mesaId;
    _impugnarIncidentId = incidentId;
    _impugnarFormId = formId;
    _impugnarMesaData = null;
    _impugnarIncidentData = null;

    const modal = document.getElementById('impugnar-modal');
    if (!modal) return;
    modal.classList.add('active');

    // Restore saved destinatario
    const savedEmail = localStorage.getItem('impugnar_destinatario') || '';
    const emailInput = document.getElementById('impugnar-email');
    if (emailInput) emailInput.value = savedEmail;

    // Reset confirm area
    const confirmArea = document.getElementById('impugnar-confirm-area');
    if (confirmArea) confirmArea.style.display = 'none';

    // Set loading states
    document.getElementById('impugnar-doc-content').innerHTML = '<div style="color:var(--muted);padding:1rem;">Generando documento…</div>';
    document.getElementById('impugnar-iframe-wrap').innerHTML = '<div style="color:var(--muted);padding:1rem;">Cargando E-14…</div>';
    document.getElementById('impugnar-modal-title').textContent = `Impugnar Mesa ${mesaId}`;

    // Find incident data from already-loaded allIncidents (no new API call)
    if (typeof allIncidents !== 'undefined' && Array.isArray(allIncidents)) {
        _impugnarIncidentData = allIncidents.find(i => i.id === incidentId || String(i.id) === String(incidentId)) || null;
    }

    // Fetch mesa detail (same call as openMesaDetail)
    try {
        const hasFormId = Number.isFinite(Number(formId));
        const isNumericMesa = /^\d+$/.test(String(mesaId));
        const e14Url = hasFormId
            ? `/api/e14-data/form/${Number(formId)}`
            : (isNumericMesa
                ? `/api/e14-data/form/${mesaId}`
                : `/api/e14-data/form-by-mesa/${mesaId}`);
        const e14Resp = await fetch(e14Url);
        if (e14Resp.ok) {
            const formData = await e14Resp.json();
            if (formData && !formData.error) {
                _impugnarMesaData = (typeof transformE14ToDetail === 'function') ? transformE14ToDetail(formData) : formData;
            }
        }
        if (!_impugnarMesaData) {
            const fallback = await fetch(`/api/campaign-team/mesa/${mesaId}/detail`);
            const fallbackData = await fallback.json();
            if (fallbackData.success) _impugnarMesaData = fallbackData.detail;
        }
    } catch (e) {
        console.warn('openImpugnarModal: error fetching mesa data', e);
    }

    // Generate document
    _impugnarDocHtml = _buildDocImpugnar(_impugnarMesaData, _impugnarIncidentData, mesaId);
    document.getElementById('impugnar-doc-content').innerHTML = _impugnarDocHtml;

    // Load PDF iframe
    const pdfUrl = _impugnarMesaData && _impugnarMesaData.pdf_url ? _impugnarMesaData.pdf_url : null;
    const iframeWrap = document.getElementById('impugnar-iframe-wrap');
    if (pdfUrl) {
        iframeWrap.innerHTML = `<iframe src="${pdfUrl}" style="width:100%;height:100%;border:none;border-radius:4px;" title="E-14 PDF"></iframe>`;
    } else {
        iframeWrap.innerHTML = '<div style="color:var(--muted);padding:1rem;font-size:0.8rem;">PDF no disponible para esta mesa.</div>';
    }
};

window.closeImpugnarModal = function() {
    const modal = document.getElementById('impugnar-modal');
    if (modal) modal.classList.remove('active');
};

// ==================== RECURSO DE IMPUGNACIÓN — documento ====================

function _ieEsc(s) { return String(s||'').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;'); }
function _ieRn(raw) { if(!raw) return ''; const s=String(raw), i=s.indexOf(' - '); return i>=0?s.slice(i+3).trim():s.trim(); }
function _ieV(val)  { return val!=null?String(val):'—'; }
function _ieBl(n)   { return `<span style="border-bottom:1px solid #555;">${'&nbsp;'.repeat(n)}</span>`; }
function _ieRow(l,v){ return `<tr><td style="padding:2px 16px 2px 0;color:#444;white-space:nowrap;vertical-align:top;">${l}</td><td style="font-weight:600;">${v}</td></tr>`; }
function _ieSec(t)  { return `<h3 style="font-size:0.84rem;font-weight:700;letter-spacing:0.4px;border-bottom:2px solid #111;padding-bottom:3px;margin:1rem 0 0.4rem;text-transform:uppercase;">${t}</h3>`; }

function _buildDocImpugnar(mesa, incident, mesaId) {
    const now   = new Date();
    const fecha = now.toLocaleDateString('es-CO', {year:'numeric',month:'long',day:'numeric'});
    const hora  = now.toLocaleTimeString('es-CO', {hour:'2-digit',minute:'2-digit'});

    const hdr     = mesa?.header || {};
    const deptRaw = _ieRn(hdr.departamento || incident?.departamento) || '—';
    const muniRaw = _ieRn(hdr.municipio    || incident?.municipio)    || '—';
    const dept    = _ieEsc(deptRaw);
    const muni    = _ieEsc(muniRaw);
    const puesto  = _ieEsc(hdr.puesto || incident?.puesto_nombre || incident?.puesto_votacion || '—');
    const zona    = hdr.zona ? String(hdr.zona).padStart(2,'0') : (incident?.zona || '—');
    const mesaNum = _ieEsc(hdr.mesa_number || incident?.mesa || '—');
    const corp    = _ieEsc(hdr.corporacion || incident?.corporacion || '—');
    const corpLabel = corp.toUpperCase().includes('SENADO') ? 'Senado de la República' : 'Cámara de Representantes';

    const sufE11     = mesa?.sufragantes_e11  ?? null;
    const totalVotos = mesa?.total_votos      ?? incident?.total_votes ?? null;
    const votosUrna  = mesa?.votos_en_urna    ?? null;
    const blancos    = mesa?.votos_blancos     ?? null;
    const nulos      = mesa?.votos_nulos       ?? null;
    const noMarcados = mesa?.votos_no_marcados ?? null;
    const conf       = mesa?.overall_confidence != null ? `${Math.round(mesa.overall_confidence*100)}%` : '—';
    const extractId  = _ieEsc(mesa?.extraction_id || mesaId || '—');
    const firmantes  = mesa?.num_jurados_firmantes ?? mesa?.jurados_firmantes ?? null;
    const warnings   = Array.isArray(mesa?.warnings)    ? mesa.warnings    : [];
    const validations= Array.isArray(mesa?.validations) ? mesa.validations : [];
    const alertsSrc  = incident?.pmsn_alerts || mesa?.pmsn_alerts || [];
    const partidos   = Array.isArray(mesa?.partidos) ? mesa.partidos : [];

    // ── Detección ──────────────────────────────────────────────────────────
    const sufN  = sufE11     != null ? Number(sufE11)     : null;
    const totN  = totalVotos != null ? Number(totalVotos) : null;
    const firmN = firmantes  != null ? Number(firmantes)  : null;
    const blaN  = blancos    != null ? Number(blancos)    : 0;
    const nulN  = nulos      != null ? Number(nulos)      : 0;
    const nomN  = noMarcados != null ? Number(noMarcados) : 0;

    const hasArith  = validations.some(v => !v.passed);
    const hasPmsn   = Array.isArray(alertsSrc) && alertsSrc.some(a => {
        const id = typeof a==='string'?a:(a.rule_id||'');
        return String(id).includes('PMSN-03')||String(id).includes('ARITH');
    });
    const hasTachon = warnings.some(w => { const t=String(w).toLowerCase(); return t.includes('tachon')||t.includes('tachón')||t.includes('enmendadura'); });

    const sumaPartidos = partidos.reduce((acc,p) => acc + (Number(p.votes??p.votos??0)||0), 0);
    const sumaTotal    = sumaPartidos + blaN + nulN + nomN;
    const diffArith    = totN != null ? sumaTotal - totN : null;
    const diffSuf      = (sufN != null && totN != null) ? sufN - totN : null;

    const DET = {
        arith:   hasArith || hasPmsn || (diffArith != null && Math.abs(diffArith) > 0),
        exceso:  sufN!==null && totN!==null && totN > sufN,
        firmas:  firmN!==null && firmN < 3,
        tachones:hasTachon,
        perdida: totN===0 && sufN!==null && sufN > 0,
    };
    const anyIrregularity = Object.values(DET).some(Boolean);

    // ── Tabla partidos ──────────────────────────────────────────────────────
    const thSt  = 'style="text-align:left;padding:4px 8px;background:#f0ede8;border-bottom:2px solid #999;"';
    const thStR = 'style="text-align:right;padding:4px 8px;background:#f0ede8;border-bottom:2px solid #999;"';
    const tdR   = 'style="text-align:right;padding:3px 8px;font-weight:600;"';
    const trOdd = 'style="border-bottom:1px solid #ddd;"';
    const trEven= 'style="border-bottom:1px solid #ddd;background:#fafafa;"';
    const _pName = p => p.party_name||p.partido_nombre||p.name||p.partido||'—';
    const _pVotes = p => p.votes??p.votos??'—';
    const partidosRows = partidos.map((p,i) =>
        `<tr ${i%2?trEven:trOdd}><td style="padding:3px 8px;">${_ieEsc(_pName(p))}</td><td ${tdR}>${_pVotes(p)}</td></tr>`
    ).join('');
    const partidosTable = partidos.length ? `
<table style="width:100%;border-collapse:collapse;font-size:0.78rem;margin:0.4rem 0;">
<thead><tr><th ${thSt}>Partido / Coalición</th><th ${thStR}>Votos</th></tr></thead>
<tbody>${partidosRows}
<tr style="font-weight:700;border-top:2px solid #999;background:#f0ede8;">
  <td style="padding:4px 8px;">Total votos partidos</td><td ${tdR}>${sumaPartidos}</td>
</tr></tbody></table>` : '';

    // ── Impacto potencial en curules ────────────────────────────────────────
    const absDiff = diffArith != null ? Math.abs(diffArith) : 0;
    const pctDiff  = (absDiff > 0 && totN > 0) ? ((absDiff / totN) * 100).toFixed(2) : null;
    const partidosBajoUmbral = partidos.filter(p => {
        const v = Number(p.votes??p.votos??0)||0;
        return v > 0 && v <= absDiff;
    });
    const impactoHtml = (absDiff > 0 && (partidosBajoUmbral.length || pctDiff)) ? `
<p style="margin:0.5rem 0;padding:7px 10px;background:#fff3e0;border-left:4px solid #e65100;font-size:0.78rem;">
<strong>Impacto potencial en el resultado:</strong> La diferencia absoluta de <strong>${absDiff} votos</strong>${pctDiff ? ` equivale al <strong>${pctDiff}%</strong> del total de la mesa (${absDiff}/${_ieV(totalVotos)})` : ''}, porcentaje suficiente para alterar la posición relativa de listas que obtuvieron votaciones inferiores o cercanas a dicho umbral${partidosBajoUmbral.length ? ` (${partidosBajoUmbral.map(p=>_ieEsc(_pName(p))+': '+_pVotes(p)+' votos').join(', ')})` : ''}, afectando eventualmente la asignación de curules o el orden de prelación dentro de la lista.
</p>` : '';

    // ── Sección III: irregularidades ────────────────────────────────────────
    let irregItems = [];

    if (DET.arith && totN != null && partidos.length) {
        // Dirección exacta: exceso o faltante
        const esExceso   = diffArith > 0;
        const esFaltante = diffArith < 0;
        const gravedad   = Math.abs(diffArith) > 5 ? ' grave' : '';
        const tipoError  = esExceso
            ? `La suma de votos detallados (<strong>${sumaTotal}</strong>) <strong>excede</strong> el total declarado en el acta (<strong>${_ieV(totalVotos)}</strong>), lo que implica que hay <strong style="color:#b71c1c;">${Math.abs(diffArith)} voto(s) contabilizados de más</strong> sin respaldo documental.`
            : esFaltante
            ? `La suma de votos detallados (<strong>${sumaTotal}</strong>) es <strong>inferior</strong> al total declarado en el acta (<strong>${_ieV(totalVotos)}</strong>), lo que implica que existen <strong style="color:#b71c1c;">${Math.abs(diffArith)} voto(s) no asignados a ninguna lista o candidato</strong>.`
            : `La suma de votos detallados coincide con el total declarado.`;
        const afectacion = esExceso
            ? 'Impide verificar la correspondencia entre votos depositados y votos distribuidos, comprometiendo la cadena de custodia documental.'
            : esFaltante
            ? 'Impide determinar a qué lista o candidato corresponden los votos no asignados, afectando la voluntad electoral real.'
            : 'No se detecta afectación aritmética en este formulario.';
        irregItems.push(`
<h4 style="font-size:0.8rem;font-weight:700;margin:0.6rem 0 0.2rem;">1. Inconsistencia aritmética${gravedad}</h4>
<p style="margin:0.2rem 0;">Del examen del formulario E-14 de la mesa ${mesaNum} se observa que:</p>
<ul style="margin:0.2rem 0 0.3rem 1.2rem;padding:0;font-size:0.78rem;">
  <li>La suma total de votos por partido asciende a <strong>${sumaPartidos} votos</strong>.</li>
  <li>Al adicionar votos en blanco (${blaN}), nulos (${nulN}) y no marcados (${nomN}), el total computable es <strong>${sumaTotal} votos</strong>.</li>
  <li>El total general de votos consignado en el acta es <strong>${_ieV(totalVotos)} votos</strong>.</li>
</ul>
<p style="margin:0.2rem 0;">${tipoError}</p>
<p style="margin:0.3rem 0 0.1rem;"><strong>Diferencia absoluta: <span style="color:#b71c1c;">${absDiff} voto(s) ${diffArith > 0 ? 'contabilizados de más' : 'no asignados a ninguna lista o candidato'}</span></strong> (${sumaTotal} − ${_ieV(totalVotos)} = ${diffArith > 0 ? '+' : ''}${diffArith})</p>
<p style="margin:0.2rem 0;font-size:0.77rem;">Esta inconsistencia: (1) rompe la coherencia interna del documento; (2) ${afectacion}; (3) genera incertidumbre sobre la verdadera voluntad electoral; (4) puede incidir en el resultado final de la corporación.</p>
${impactoHtml}`);
    } else if (DET.arith) {
        const failDetails = validations.filter(v=>!v.passed);
        const detailStr = failDetails.length
            ? failDetails.map(v=>`${_ieEsc(v.check||'')}: ${_ieEsc(v.detail||'')}`).join('; ')
            : alertsSrc.map(a=>typeof a==='string'?a:(a.description||a.message||a.rule_id||'')).filter(Boolean).join('; ');
        irregItems.push(`
<h4 style="font-size:0.8rem;font-weight:700;margin:0.6rem 0 0.2rem;">1. Inconsistencia aritmética</h4>
<p style="margin:0.2rem 0;">Se detectaron errores en la validación del acta: <strong style="color:#b71c1c;">${_ieEsc(detailStr) || 'ver alertas sistema'}</strong>.</p>
<p style="margin:0.2rem 0;font-size:0.77rem;">Este tipo de inconsistencia compromete la coherencia interna del documento electoral e impide verificar la correspondencia entre los votos depositados y los asignados.</p>`);
    }

    if (DET.exceso && diffSuf != null) {
        const n = irregItems.length + 1;
        irregItems.push(`
<h4 style="font-size:0.8rem;font-weight:700;margin:0.6rem 0 0.2rem;">${n}. Exceso de votos sobre sufragantes</h4>
<p style="margin:0.2rem 0;">Sufragantes registrados en E-11: <strong>${_ieV(sufE11)}</strong>. Total votos computados (E-14): <strong>${_ieV(totalVotos)}</strong>. Diferencia: <strong style="color:#b71c1c;">${Math.abs(diffSuf)} voto(s) en exceso</strong>.</p>
<p style="margin:0.2rem 0;font-size:0.77rem;">El número de votos computados supera el de ciudadanos que ejercieron el sufragio, lo que es materialmente imposible y configura una irregularidad estructural en la cadena de custodia documental.</p>`);
    }

    if (DET.firmas) {
        const n = irregItems.length + 1;
        irregItems.push(`
<h4 style="font-size:0.8rem;font-weight:700;margin:0.6rem 0 0.2rem;">${n}. Insuficiencia de firmas de jurados</h4>
<p style="margin:0.2rem 0;">El acta registra <strong style="color:#b71c1c;">${_ieV(firmantes)} firma(s)</strong> de jurado(s). El artículo 192 numeral 3 del Código Electoral exige mínimo tres (3) firmas para la validez del documento. La ausencia de firmas requeridas compromete la autenticidad del acta.</p>`);
    }

    if (DET.tachones) {
        const tachList = warnings.filter(w=>{ const t=String(w).toLowerCase(); return t.includes('tachon')||t.includes('tachón')||t.includes('enmendadura'); });
        const n = irregItems.length + 1;
        irregItems.push(`
<h4 style="font-size:0.8rem;font-weight:700;margin:0.6rem 0 0.2rem;">${n}. Tachones y enmendaduras sin nota aclaratoria</h4>
<p style="margin:0.2rem 0;">Se detectaron alteraciones en el acta sin nota aclaratoria de los jurados: <strong>${tachList.map(w=>_ieEsc(w)).join('; ') || 'ver advertencias del sistema'}</strong>. Conforme al artículo 163 del Código Electoral, toda corrección debe ser certificada expresamente por los jurados.</p>`);
    }

    const irregHtml = irregItems.length
        ? irregItems.join('')
        : `<p style="color:#555;font-style:italic;">No se detectaron irregularidades automáticas. Complemente con los hechos observados directamente.</p>`;

    // ── Fundamentos ──────────────────────────────────────────────────────────
    const activeRjIds = new Set();
    if (DET.arith)    activeRjIds.add('RJ-03');
    if (DET.exceso)   activeRjIds.add('RJ-01');
    if (DET.firmas)   activeRjIds.add('RJ-06');
    if (DET.tachones) activeRjIds.add('RJ-05');
    if (DET.perdida)  activeRjIds.add('RJ-04');

    alertsSrc.forEach(a => {
        const pmsnId = typeof a === 'string' ? a : (a.rule_id || '');
        (PMSN_TO_RJ[pmsnId] || []).forEach(rj => activeRjIds.add(rj));
    });

    if (anyIrregularity) activeRjIds.add('RJ-03');

    const fundsItems = [...activeRjIds].map(rjId => {
        const r = REGLAS_JURIDICAS[rjId] || {};
        const arts = (r.articulos || []).map(a =>
            `${a.norma}, artículo ${a.articulo}${a.numeral ? `, numeral ${a.numeral}` : ''}`
        ).join(' — ');
        return `<li style="margin-bottom:5px;"><strong>${arts}</strong> — ${_ieEsc(r.nombre || rjId)}: ${_ieEsc(r.descripcion || '')}. <em>Tipo: ${_ieEsc(r.tipo || '')}. Gravedad: ${_ieEsc(r.gravedad || '')}.</em></li>`;
    }).join('');

    // ── Naturaleza de la anomalía ─────────────────────────────────────────────
    const natDirStr = (DET.arith && diffArith != null && partidos.length)
        ? (diffArith > 0
            ? `la suma de votos detallados (${sumaTotal}) supera el total declarado en el acta (${_ieV(totalVotos)}), con ${absDiff} voto(s) sin respaldo documental`
            : diffArith < 0
            ? `la suma de votos detallados (${sumaTotal}) es inferior al total declarado (${_ieV(totalVotos)}), con ${absDiff} voto(s) no asignados a ninguna lista o candidato`
            : 'los datos del acta presentan inconsistencias en su validación')
        : 'se verifican las irregularidades descritas en la sección anterior';

    const custodiaHtml = DET.arith ? `
<p style="margin:0.3rem 0;font-size:0.77rem;">La existencia de votos ${diffArith > 0 ? 'sin respaldo documental' : 'no asignados'} compromete la trazabilidad documental del escrutinio, pues impide establecer correspondencia entre votos depositados, votos contabilizados y votos distribuidos, afectando la integridad del documento electoral como medio probatorio.</p>` : '';

    // ── Relevancia material ───────────────────────────────────────────────────
    const relevanciaHtml = (DET.arith || DET.exceso) ? `
${_ieSec('V. Relevancia material de la inconsistencia')}
<p style="margin:0.2rem 0;">La inconsistencia aritmética detectada:</p>
<ol style="margin:0.2rem 0 0.3rem 1.2rem;padding:0;font-size:0.78rem;">
  <li style="margin-bottom:3px;">No puede considerarse error menor o formal.</li>
  <li style="margin-bottom:3px;">Supera el margen de tolerancia aceptable en escrutinios de mesa.</li>
  <li style="margin-bottom:3px;">Impide verificar la correspondencia exacta entre sufragantes (${_ieV(sufE11)}), votos en urna (${_ieV(votosUrna)}) y votos asignados (${sumaPartidos}).</li>
  <li style="margin-bottom:3px;">Afecta directamente la certeza del resultado electoral.</li>
</ol>
<p style="margin:0.3rem 0;padding:6px 10px;background:#fce4e4;border-left:4px solid #b71c1c;font-size:0.78rem;">
En materia electoral, el estándar no es la simple probabilidad sino la <strong>certeza documental</strong>. Cuando el acta no es matemáticamente coherente, pierde presunción de legalidad hasta tanto sea verificada materialmente por la autoridad competente.
</p>` : '';

    // ── Petición ──────────────────────────────────────────────────────────────
    const petItems = [
        `<li style="margin-bottom:4px;">La verificación física e integral del formulario E-14 original correspondiente a la mesa ${mesaNum}, Zona ${_ieEsc(zona)}, ${puesto}, ${muni}.</li>`,
        `<li style="margin-bottom:4px;">La confrontación del E-14 con el E-11 y demás documentos electorales de la mesa.</li>`,
        ...(DET.arith||DET.exceso ? [`<li style="margin-bottom:4px;">La práctica de recuento de votos si la verificación material lo amerita.</li>`] : []),
        ...(DET.arith   ? [`<li style="margin-bottom:4px;">La adopción de las correcciones aritméticas correspondientes en el acta de escrutinio.</li>`] : []),
        `<li style="margin-bottom:4px;">La suspensión del cómputo provisional de la mesa hasta tanto se adopte decisión motivada sobre la presente impugnación, a fin de evitar consolidaciones irreversibles del resultado.</li>`,
        `<li style="margin-bottom:4px;">Que la decisión que resuelva la presente impugnación sea debidamente motivada en derecho y consignada en el acta general de escrutinio.</li>`,
    ].join('');

    // ── Ensamble ──────────────────────────────────────────────────────────────
    const trZ = (l,v,z) => `<tr${z?' style="background:#f5f5f5;"':''}><td style="padding:3px 10px;color:#444;width:42%;">${l}</td><td style="padding:3px 10px;font-weight:600;">${v}</td></tr>`;
    const corpCap = corpLabel.toUpperCase();
    return `<div style="font-family:'Times New Roman',Georgia,serif;font-size:0.82rem;line-height:1.6;color:#111;max-width:720px;">

<div style="text-align:center;margin-bottom:0.8rem;">
  <div style="font-weight:700;font-size:1.1rem;letter-spacing:1.5px;border-bottom:3px double #111;padding-bottom:6px;margin-bottom:4px;">RECURSO DE IMPUGNACIÓN</div>
  <div style="font-size:0.78rem;color:#444;">(Proceso de Escrutinio Electoral)</div>
</div>

<p style="margin:0.6rem 0 1rem;"><strong>Señora Presidenta / Señores Integrantes<br>
COMISIÓN ESCRUTADORA DE ${dept.toUpperCase()}<br>
Congreso de la República – ${_ieEsc(corpLabel)}<br>
E. S. D.</strong></p>

<table style="width:100%;border-collapse:collapse;margin-bottom:1rem;border:1px solid #ccc;font-size:0.78rem;">
${trZ('Fecha',fecha+' – '+hora,false)}
${trZ('Corporación',_ieEsc(corpLabel),true)}
${trZ('Proceso Electoral','Congreso de la República – 13 de marzo de 2022',false)}
${trZ('Departamento',dept,true)}
${trZ('Municipio / Distrito',muni,false)}
${trZ('Puesto / Localidad',puesto,true)}
${trZ('Zona',_ieEsc(zona),false)}
${trZ('Mesa',mesaNum,true)}
</table>

${_ieSec('I. Información de la Mesa – Datos consignados en formularios')}
<table style="width:100%;border-collapse:collapse;font-size:0.78rem;margin:0.4rem 0;border:1px solid #ddd;">
${trZ('Sufragantes (E-11)',_ieV(sufE11),false)}
${trZ('Votos en la urna',_ieV(votosUrna),true)}
${trZ('Total votos computados (E-14)','<strong>'+_ieV(totalVotos)+'</strong>',false)}
${trZ('Votos en blanco',_ieV(blancos),true)}
${trZ('Votos nulos',_ieV(nulos),false)}
${trZ('Votos no marcados',_ieV(noMarcados),true)}
</table>

${partidos.length ? _ieSec('II. Votación por partido / coalición')+'<p style="font-size:0.75rem;color:#555;margin:0.1rem 0 0.3rem;">(Según registro consignado en formulario E-14)</p>'+partidosTable : ''}

${_ieSec('III. Irregularidades objetivamente verificables')}
${irregHtml}

${_ieSec('IV. Naturaleza de la anomalía')}
<p style="margin:0.2rem 0;">La inconsistencia detectada no corresponde a un error atribuible a sistemas externos, sino a una divergencia estructural en el acta E-14: ${natDirStr}. Esta situación:</p>
<ol style="margin:0.2rem 0 0.3rem 1.2rem;padding:0;font-size:0.78rem;">
  <li style="margin-bottom:3px;">Rompe la coherencia interna del documento electoral.</li>
  <li style="margin-bottom:3px;">Impide determinar con certeza la voluntad electoral real de los sufragantes.</li>
  <li style="margin-bottom:3px;">Afecta la cadena de custodia documental del material electoral.</li>
  <li style="margin-bottom:3px;">Puede incidir en el resultado final de la corporación y en la asignación de curules.</li>
</ol>
${custodiaHtml}

${relevanciaHtml}

${_ieSec('VI. Fundamentos de derecho')}
<p style="margin:0.2rem 0 0.3rem;">La presente impugnación se sustenta en:</p>
<ul style="margin:0 0 0.4rem 1.2rem;padding:0;">${fundsItems}</ul>
<p style="font-size:0.76rem;margin:0.3rem 0;">Las inconsistencias verificadas constituyen causal suficiente para ordenar la verificación material del documento y, de ser procedente, la apertura de la urna y el recuento de votos, en garantía del principio de verdad material del escrutinio.</p>

${_ieSec('VII. Petición')}
<p style="margin:0.2rem 0 0.3rem;">Respetuosamente se solicita a la autoridad electoral competente:</p>
<ol style="margin:0 0 0.4rem 1.2rem;padding:0;">${petItems}</ol>

<p style="margin:0.6rem 0;font-size:0.78rem;font-style:italic;border-top:1px solid #ddd;padding-top:0.4rem;">
<strong>Reserva de acciones:</strong> El presentante se reserva expresamente el derecho de acudir a los medios de control previstos en el CPACA y ante el Consejo de Estado en caso de no prosperar la presente impugnación o de no adoptarse las medidas solicitadas.
</p>

<div style="margin-top:2rem;">
<p style="font-size:0.78rem;margin:0 0 0.5rem;">Atentamente,</p>
<div style="border-bottom:1px solid #333;width:320px;height:32px;margin:0 0 0.3rem;"></div>
<table style="font-size:0.78rem;border-collapse:collapse;margin-bottom:0.5rem;">
${_ieRow('Nombre:',        _ieBl(44))}
${_ieRow('C.C.:',          _ieBl(24))}
${_ieRow('Calidad:',       '&#9744; Testigo electoral &nbsp; &#9744; Apoderado &nbsp; &#9744; Candidato &nbsp; &#9744; Delegado de partido')}
${_ieRow('Partido / Org.:', _ieBl(30))}
${_ieRow('Teléfono:',      _ieBl(24))}
</table>
</div>

<div style="font-size:0.65rem;color:#888;border-top:1px solid #ddd;padding-top:4px;margin-top:10px;">
Generado por CASTOR Elecciones — ${fecha} ${hora}
</div></div>`;
}


window.descargarImpugnacion = function() {
    if (!_impugnarDocHtml) return;
    const css = `@page{size:A4;margin:2cm;}body{font-family:'Courier New',monospace;font-size:10pt;line-height:1.5;color:#111;margin:0;padding:0;}table{border-collapse:collapse;}@media print{body{-webkit-print-color-adjust:exact;print-color-adjust:exact;}}`;
    const html = `<!DOCTYPE html><html lang="es"><head><meta charset="utf-8"><title>Reclamación Electoral Mesa ${_impugnarMesaId}</title><style>${css}</style></head><body>${_impugnarDocHtml}</body></html>`;
    const iframe = document.createElement('iframe');
    iframe.style.cssText = 'position:fixed;top:-9999px;left:-9999px;width:1px;height:1px;border:none;';
    document.body.appendChild(iframe);
    const doc = iframe.contentDocument || iframe.contentWindow.document;
    doc.open(); doc.write(html); doc.close();
    setTimeout(() => {
        iframe.contentWindow.focus();
        iframe.contentWindow.print();
        setTimeout(() => document.body.removeChild(iframe), 3000);
    }, 400);
};

window.iniciarEnvioImpugnacion = function() {
    const emailInput = document.getElementById('impugnar-email');
    const email = emailInput ? emailInput.value.trim() : '';
    if (!email) { if (emailInput) emailInput.focus(); return; }
    document.getElementById('impugnar-confirm-email-text').textContent = email;
    const confirmArea = document.getElementById('impugnar-confirm-area');
    if (confirmArea) confirmArea.style.display = 'flex';
};

window.cancelarEnvioImpugnacion = function() {
    const confirmArea = document.getElementById('impugnar-confirm-area');
    if (confirmArea) confirmArea.style.display = 'none';
};

window.confirmarEnvioImpugnacion = async function() {
    const emailInput = document.getElementById('impugnar-email');
    const email = emailInput ? emailInput.value.trim() : '';
    if (!email || !_impugnarDocHtml) return;

    localStorage.setItem('impugnar_destinatario', email);

    // Build full HTML document to attach
    const css = `@page{size:A4;margin:2cm;}body{font-family:'Times New Roman',Georgia,serif;font-size:10pt;line-height:1.6;color:#111;margin:0;padding:0;}table{border-collapse:collapse;}@media print{body{-webkit-print-color-adjust:exact;print-color-adjust:exact;}}`;
    const htmlDoc = `<!DOCTYPE html><html lang="es"><head><meta charset="utf-8"><title>Recurso de Impugnación Mesa ${_impugnarMesaId}</title><style>${css}</style></head><body>${_impugnarDocHtml}</body></html>`;

    // Close confirm area & show spinner
    const confirmArea = document.getElementById('impugnar-confirm-area');
    if (confirmArea) confirmArea.style.display = 'none';

    const btnEnviar = document.querySelector('[onclick="iniciarEnvioImpugnacion()"]');
    const originalText = btnEnviar ? btnEnviar.textContent : '';
    if (btnEnviar) { btnEnviar.textContent = 'Enviando…'; btnEnviar.disabled = true; }

    try {
        const resp = await fetch('/api/campaign-team/send-impugnacion', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({
                destinatario: email,
                mesa_id: _impugnarMesaId || 'MESA',
                incident_id: _impugnarIncidentId,
                form_id: _impugnarFormId,
                html_doc: htmlDoc,
            }),
        });
        const result = await resp.json();
        const ok = result.success === true;
        const toast = document.createElement('div');
        toast.textContent = ok
            ? `✓ Impugnación enviada a ${email}`
            : `✗ Error al enviar: ${result.error || 'intente de nuevo'}`;
        toast.style.cssText = `position:fixed;bottom:1.5rem;right:1.5rem;background:${ok?'#166534':'#991B1B'};color:#fff;padding:0.75rem 1.3rem;border-radius:6px;font-size:0.85rem;z-index:9999;box-shadow:0 2px 10px rgba(0,0,0,0.35);`;
        document.body.appendChild(toast);
        setTimeout(() => toast.remove(), ok ? 4000 : 6000);
    } catch (err) {
        const toast = document.createElement('div');
        toast.textContent = `✗ Error de red: ${err.message}`;
        toast.style.cssText = 'position:fixed;bottom:1.5rem;right:1.5rem;background:#991B1B;color:#fff;padding:0.75rem 1.3rem;border-radius:6px;font-size:0.85rem;z-index:9999;';
        document.body.appendChild(toast);
        setTimeout(() => toast.remove(), 6000);
    } finally {
        if (btnEnviar) { btnEnviar.textContent = originalText; btnEnviar.disabled = false; }
    }
};

// ==================== UPLOAD ACTA E-14 ====================
// Front-only branch: OCR upload disabled.
window.uploadActaE14 = async function(input) {
    if (input) input.value = '';
};
