const statusLabels = {
  pending: "Pendiente",
  won: "Ganada",
  lost: "Perdida",
  push: "Push",
  void: "Anulada",
};

const elements = {
  scanButton: document.querySelector("#scan-button"),
  scanLabel: document.querySelector("#scan-label"),
  syncButton: document.querySelector("#sync-button"),
  liveStatus: document.querySelector("#live-status"),
  hitRate: document.querySelector("#hit-rate"),
  sampleSize: document.querySelector("#sample-size"),
  wonCount: document.querySelector("#won-count"),
  lostCount: document.querySelector("#lost-count"),
  pendingCount: document.querySelector("#pending-count"),
  pickList: document.querySelector("#pick-list"),
  historyList: document.querySelector("#history-list"),
};

function percentage(value) {
  if (typeof value !== "number" || !Number.isFinite(value)) return "—";
  return `${Math.round(value * 100)}%`;
}

function dateLabel(value) {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "Fecha por confirmar";
  return new Intl.DateTimeFormat("es-MX", {
    day: "numeric",
    month: "short",
    hour: "2-digit",
    minute: "2-digit",
  }).format(date);
}

function numberLabel(value, digits = 2) {
  const number = Number(value);
  return Number.isFinite(number) ? number.toFixed(digits) : "—";
}

function createEmptyState(message) {
  const state = document.createElement("div");
  state.className = "empty-state";
  state.textContent = message;
  return state;
}

function updateSummary(summary = {}) {
  const settled = Number(summary.settled) || 0;
  elements.hitRate.textContent = settled ? percentage(summary.hit_rate) : "—";
  elements.sampleSize.textContent = settled
    ? `${settled} selecciones resueltas`
    : "Sin resultados resueltos";
  elements.wonCount.textContent = String(Number(summary.won) || 0);
  elements.lostCount.textContent = String(Number(summary.lost) || 0);
  elements.pendingCount.textContent = String(Number(summary.pending) || 0);
}

function renderPicks(picks = []) {
  elements.pickList.replaceChildren();
  if (!picks.length) {
    elements.pickList.append(createEmptyState("No hay selecciones con valor para mostrar. Prueba una nueva búsqueda más tarde."));
    return;
  }

  picks.slice(0, 5).forEach((pick, index) => {
    const card = document.createElement("article");
    card.className = "pick-card";

    const description = document.createElement("div");
    description.className = "pick-description";
    const match = document.createElement("div");
    const rank = document.createElement("span");
    rank.className = "pick-rank";
    rank.textContent = `0${index + 1}`;
    const teams = document.createElement("span");
    teams.className = "match-name";
    teams.textContent = `${pick.home_team} vs ${pick.away_team}`;
    match.append(rank, teams);
    const meta = document.createElement("div");
    meta.className = "pick-meta";
    meta.textContent = `${dateLabel(pick.kickoff)} · ${pick.stats_season || "2024"} histórico`;
    const selection = document.createElement("div");
    selection.className = "pick-selection";
    selection.textContent = pick.selection;
    const bookmaker = document.createElement("div");
    bookmaker.className = "pick-bookmaker";
    bookmaker.textContent = `${pick.bookmaker} · ${pick.odds_region || "US"}`;
    description.append(match, meta, selection, bookmaker);

    const numbers = document.createElement("div");
    numbers.className = "pick-numbers";
    const odds = document.createElement("div");
    odds.className = "pick-number";
    const oddsValue = document.createElement("strong");
    oddsValue.textContent = numberLabel(pick.odds);
    const oddsLabel = document.createElement("span");
    oddsLabel.textContent = "Cuota";
    odds.append(oddsValue, oddsLabel);

    const implied = document.createElement("div");
    implied.className = "pick-number";
    const impliedValue = document.createElement("strong");
    impliedValue.textContent = percentage(pick.implied_probability);
    const impliedLabel = document.createElement("span");
    impliedLabel.textContent = "Prob. implícita";
    implied.append(impliedValue, impliedLabel);

    const model = document.createElement("div");
    model.className = "pick-number";
    const modelProbability = Number(pick.model_probability);
    const pushProbability = Number(pick.push_probability) || 0;
    const modelValue = document.createElement("strong");
    modelValue.textContent = percentage(modelProbability);
    const modelLabel = document.createElement("span");
    modelLabel.textContent = "Prob. ganar";
    model.append(modelValue, modelLabel);
    const loss = document.createElement("div");
    loss.className = "pick-number";
    const lossValue = document.createElement("strong");
    lossValue.textContent = percentage(Math.max(0, 1 - modelProbability - pushProbability));
    const lossLabel = document.createElement("span");
    lossLabel.textContent = "Prob. perder";
    loss.append(lossValue, lossLabel);
    numbers.append(odds, implied, model, loss);
    if (pushProbability > 0) {
      const push = document.createElement("div");
      push.className = "pick-number";
      const pushValue = document.createElement("strong");
      pushValue.textContent = percentage(pushProbability);
      const pushLabel = document.createElement("span");
      pushLabel.textContent = "Push";
      push.append(pushValue, pushLabel);
      numbers.append(push);
    }

    const edge = document.createElement("div");
    edge.className = "pick-value";
    const edgeMetric = document.createElement("div");
    edgeMetric.className = "pick-number";
    const edgeValue = document.createElement("strong");
    edgeValue.textContent = percentage(pick.edge);
    const edgeLabel = document.createElement("span");
    edgeLabel.textContent = pushProbability > 0 ? "Edge vs cuota (sin push)" : "Edge vs cuota";
    edgeMetric.append(edgeValue, edgeLabel);
    const expectedValue = document.createElement("div");
    expectedValue.className = "pick-number";
    const expectedValueNumber = document.createElement("strong");
    expectedValueNumber.textContent = percentage(pick.expected_value);
    const expectedValueLabel = document.createElement("span");
    expectedValueLabel.textContent = "EV modelo / unidad";
    expectedValue.append(expectedValueNumber, expectedValueLabel);
    edge.append(edgeMetric, expectedValue);

    card.append(description, numbers, edge);
    elements.pickList.append(card);
  });
}

function renderHistory(history = []) {
  elements.historyList.replaceChildren();
  if (!history.length) {
    elements.historyList.append(createEmptyState("Aún no hay selecciones guardadas."));
    return;
  }

  history.forEach((pick) => {
    const row = document.createElement("article");
    row.className = "history-row";
    const main = document.createElement("div");
    main.className = "history-main";
    const match = document.createElement("div");
    match.className = "history-match";
    match.textContent = `${pick.home_team} vs ${pick.away_team}`;
    const selection = document.createElement("div");
    selection.className = "history-pick";
    selection.textContent = `${pick.selection} · ${dateLabel(pick.kickoff)}`;
    main.append(match, selection);

    const odds = document.createElement("div");
    odds.className = "history-odds";
    odds.textContent = `Cuota ${numberLabel(pick.odds)}`;
    const status = document.createElement("span");
    status.className = `status-pill status-${pick.status}`;
    status.textContent = statusLabels[pick.status] || "Desconocido";
    row.append(main, odds, status);
    elements.historyList.append(row);
  });
}

async function requestJson(path, options = {}) {
  const response = await fetch(path, {
    ...options,
    headers: { accept: "application/json", ...options.headers },
  });
  let payload;
  try {
    payload = await response.json();
  } catch {
    throw new Error("El servidor devolvió una respuesta inválida.");
  }
  if (!response.ok) {
    throw new Error(payload.error || `No se pudo completar la solicitud (${response.status}).`);
  }
  return payload;
}

async function refreshDashboard() {
  const dashboard = await requestJson("/api/dashboard");
  updateSummary(dashboard.summary);
  renderPicks(dashboard.top_picks);
  renderHistory(dashboard.history);
}

function setStatus(message, kind = "") {
  elements.liveStatus.textContent = message;
  elements.liveStatus.dataset.kind = kind;
}

async function scanMatches() {
  elements.scanButton.disabled = true;
  elements.syncButton.disabled = true;
  elements.scanLabel.textContent = "Buscando partidos...";
  setStatus("Consultando cuotas y estadísticas históricas. Puede tardar unos segundos.");
  try {
    const result = await requestJson("/api/analyze", { method: "POST" });
    renderPicks(result.picks);
    await refreshDashboard();
    const suffix = result.picks_saved === 1 ? "selección nueva guardada" : "selecciones nuevas guardadas";
    setStatus(
      `${result.events_analyzed} partidos analizados · ${result.picks_saved} ${suffix} · temporada ${result.stats_season}, región ${result.odds_region.toUpperCase()}.`,
      "success",
    );
  } catch (error) {
    setStatus(error.message || "No se pudo completar la búsqueda.", "error");
  } finally {
    elements.scanButton.disabled = false;
    elements.syncButton.disabled = false;
    elements.scanLabel.textContent = "Buscar próximos partidos";
  }
}

async function syncResults() {
  elements.syncButton.disabled = true;
  elements.scanButton.disabled = true;
  setStatus("Actualizando resultados de partidos finalizados...");
  try {
    const result = await requestJson("/api/sync", { method: "POST" });
    await refreshDashboard();
    setStatus(`${result.picks_settled} selecciones actualizadas.`, "success");
  } catch (error) {
    setStatus(error.message || "No se pudieron actualizar los resultados.", "error");
  } finally {
    elements.syncButton.disabled = false;
    elements.scanButton.disabled = false;
  }
}

elements.scanButton.addEventListener("click", scanMatches);
elements.syncButton.addEventListener("click", syncResults);

refreshDashboard().catch((error) => {
  setStatus(error.message || "No se pudo cargar el historial.", "error");
});
