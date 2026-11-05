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
  standingsSeason: document.querySelector("#standings-season"),
  standingsStatus: document.querySelector("#standings-status"),
  standingsList: document.querySelector("#standings-list"),
  fixturesStatus: document.querySelector("#fixtures-status"),
  fixturesList: document.querySelector("#fixtures-list"),
  fixtureDetail: document.querySelector("#fixture-detail"),
};

const outcomeLabels = {
  home_win: "Gana local",
  draw: "Empate",
  away_win: "Gana visitante",
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

    const selectedOutcome = pick.market_key === "h2h"
      ? pick.outcome_key === "home"
        ? pick.home_team
        : pick.outcome_key === "away"
          ? pick.away_team
          : "Empate"
      : pick.selection;
    const losingOutcome = pick.market_key === "h2h"
      ? pick.outcome_key === "home"
        ? `No gana ${pick.home_team}`
        : pick.outcome_key === "away"
          ? `No gana ${pick.away_team}`
          : "No hay empate"
      : `No se cumple “${pick.selection}”`;

    const model = document.createElement("div");
    model.className = "pick-number";
    const modelProbability = Number(pick.model_probability);
    const pushProbability = Number(pick.push_probability) || 0;
    const modelValue = document.createElement("strong");
    modelValue.textContent = percentage(modelProbability);
    const modelLabel = document.createElement("span");
    modelLabel.textContent = `Gana: ${selectedOutcome}`;
    model.append(modelValue, modelLabel);
    const loss = document.createElement("div");
    loss.className = "pick-number";
    const lossValue = document.createElement("strong");
    lossValue.textContent = percentage(Math.max(0, 1 - modelProbability - pushProbability));
    const lossLabel = document.createElement("span");
    lossLabel.textContent = `Pierde: ${losingOutcome}`;
    loss.append(lossValue, lossLabel);
    numbers.append(odds, implied, model, loss);
    if (pushProbability > 0) {
      const push = document.createElement("div");
      push.className = "pick-number";
      const pushValue = document.createElement("strong");
      pushValue.textContent = percentage(pushProbability);
      const pushLabel = document.createElement("span");
      pushLabel.textContent = "Push (se devuelve)";
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

function addTeamLogo(container, url, className = "team-logo") {
  if (!url) return;
  const image = document.createElement("img");
  image.className = className;
  image.src = url;
  image.alt = "";
  image.loading = "lazy";
  image.addEventListener("error", () => image.remove(), { once: true });
  container.append(image);
}

function renderStandings(rows = []) {
  elements.standingsList.replaceChildren();
  elements.standingsStatus.dataset.kind = "";
  if (!rows.length) {
    elements.standingsStatus.textContent = "La tabla no está disponible para esta temporada.";
    return;
  }
  elements.standingsStatus.textContent = "";
  rows.forEach((team) => {
    const row = document.createElement("tr");
    const values = [
      team.rank ?? "—",
      team.team || "Equipo sin nombre",
      team.played ?? "—",
      team.won ?? "—",
      team.drawn ?? "—",
      team.lost ?? "—",
      team.goal_difference ?? "—",
      team.points ?? "—",
    ];
    values.forEach((value, index) => {
      const cell = document.createElement("td");
      if (index === 1) {
        const content = document.createElement("span");
        content.className = "standing-team";
        addTeamLogo(content, team.logo);
        const name = document.createElement("span");
        name.textContent = String(value);
        content.append(name);
        cell.append(content);
      } else {
        cell.textContent = String(value);
      }
      row.append(cell);
    });
    elements.standingsList.append(row);
  });
}

function createProbabilityRow(label, probability, likely) {
  const row = document.createElement("div");
  row.className = `probability-row${likely ? " is-likely" : ""}`;
  const name = document.createElement("span");
  name.textContent = label;
  const track = document.createElement("span");
  track.className = "probability-track";
  const fill = document.createElement("span");
  fill.className = "probability-fill";
  fill.style.display = "block";
  fill.style.width = `${Math.max(0, Math.min(100, Number(probability) * 100))}%`;
  track.append(fill);
  const percent = document.createElement("strong");
  percent.textContent = percentage(probability);
  row.append(name, track, percent);
  return row;
}

function renderFixtures(fixtures = [], minimumFormMatches = 3) {
  elements.fixturesList.replaceChildren();
  elements.fixturesStatus.dataset.kind = "";
  if (!fixtures.length) {
    elements.fixturesStatus.textContent = "No hay partidos próximos disponibles.";
    return;
  }
  elements.fixturesStatus.textContent = "";
  fixtures.forEach((fixture) => {
    const card = document.createElement("article");
    card.className = "fixture-card";
    const topline = document.createElement("div");
    topline.className = "fixture-topline";
    const kickoff = document.createElement("span");
    kickoff.textContent = dateLabel(fixture.kickoff);
    const status = document.createElement("span");
    status.textContent = fixture.status || fixture.round || "Liga MX";
    topline.append(kickoff, status);

    const teams = document.createElement("div");
    teams.className = "fixture-team-line";
    const home = document.createElement("span");
    home.className = "fixture-team";
    addTeamLogo(home, fixture.home_team?.logo);
    const homeName = document.createElement("span");
    homeName.textContent = fixture.home_team?.name || "Local";
    home.append(homeName);
    const score = document.createElement("span");
    score.className = "fixture-score";
    score.textContent = fixture.home_goals == null && fixture.away_goals == null
      ? "vs"
      : `${fixture.home_goals ?? "—"} - ${fixture.away_goals ?? "—"}`;
    const away = document.createElement("span");
    away.className = "fixture-team";
    addTeamLogo(away, fixture.away_team?.logo);
    const awayName = document.createElement("span");
    awayName.textContent = fixture.away_team?.name || "Visitante";
    away.append(awayName);
    teams.append(home, score, away);

    const detailButton = document.createElement("button");
    detailButton.className = "match-detail-button";
    detailButton.type = "button";
    detailButton.dataset.fixtureId = String(fixture.id);
    detailButton.textContent = "Ver detalle";
    const actions = document.createElement("div");
    actions.className = "fixture-actions";
    if (fixture.prediction) {
      const label = document.createElement("div");
      label.className = "prediction-label";
      const mostLikely = document.createElement("strong");
      mostLikely.textContent = outcomeLabels[fixture.prediction.likely_outcome] || "Pronóstico";
      const source = document.createElement("span");
      source.textContent = `Últimos ${fixture.form_sample.home}/${fixture.form_sample.away} partidos`;
      label.append(mostLikely, source);
      const probabilities = document.createElement("div");
      probabilities.className = "probability-list";
      ["home_win", "draw", "away_win"].forEach((key) => {
        probabilities.append(
          createProbabilityRow(
            outcomeLabels[key],
            fixture.prediction[key],
            fixture.prediction.likely_outcome === key,
          ),
        );
      });
      card.append(topline, teams, label, probabilities);
    } else {
      const unavailable = document.createElement("p");
      unavailable.className = "form-sample";
      unavailable.textContent = `Pronóstico no disponible: se requieren al menos ${minimumFormMatches} resultados recientes por equipo.`;
      card.append(topline, teams, unavailable);
    }
    actions.append(detailButton);
    card.append(actions);
    elements.fixturesList.append(card);
  });
}

function detailBlock(title, rows) {
  const block = document.createElement("section");
  block.className = "detail-data-block";
  const heading = document.createElement("h3");
  heading.textContent = title;
  block.append(heading);
  if (!rows.length) {
    const empty = document.createElement("p");
    empty.className = "form-sample";
    empty.textContent = "Aún no disponible.";
    block.append(empty);
    return block;
  }
  rows.forEach(([label, value]) => {
    const row = document.createElement("div");
    row.className = "detail-data-row";
    const name = document.createElement("span");
    name.textContent = String(label);
    const content = document.createElement("strong");
    content.textContent = String(value ?? "—");
    row.append(name, content);
    block.append(row);
  });
  return block;
}

function renderFixtureDetail(detail) {
  elements.fixtureDetail.replaceChildren();
  const header = document.createElement("div");
  header.className = "fixture-detail-teams";
  const home = document.createElement("span");
  home.className = "fixture-detail-team";
  addTeamLogo(home, detail.home_logo, "team-logo");
  const homeName = document.createElement("span");
  homeName.textContent = detail.home_team || "Local";
  home.append(homeName);
  const score = document.createElement("span");
  score.className = "fixture-detail-score";
  score.textContent = detail.home_goals == null && detail.away_goals == null
    ? "vs"
    : `${detail.home_goals ?? "—"} - ${detail.away_goals ?? "—"}`;
  const away = document.createElement("span");
  away.className = "fixture-detail-team";
  addTeamLogo(away, detail.away_logo, "team-logo");
  const awayName = document.createElement("span");
  awayName.textContent = detail.away_team || "Visitante";
  away.append(awayName);
  header.append(home, score, away);

  const meta = document.createElement("div");
  meta.className = "detail-meta";
  [dateLabel(detail.kickoff), detail.status, detail.venue, detail.city, detail.referee]
    .filter(Boolean)
    .forEach((value) => {
      const item = document.createElement("span");
      item.textContent = String(value);
      meta.append(item);
    });

  const grid = document.createElement("div");
  grid.className = "detail-data-grid";
  const eventRows = (detail.events || []).map((event) => [
    `${event.time?.elapsed ?? ""}' ${event.team?.name || ""}`,
    [event.player?.name, event.detail].filter(Boolean).join(" · ") || event.type || "Evento",
  ]);
  grid.append(detailBlock("Eventos", eventRows));

  const statsRows = (detail.statistics || []).flatMap((teamStats) => {
    const teamName = teamStats.team?.name || "Equipo";
    return (teamStats.statistics || []).map((stat) => [
      `${teamName} · ${stat.type || "Estadística"}`,
      stat.value,
    ]);
  });
  grid.append(detailBlock("Estadísticas", statsRows));

  const lineupRows = (detail.lineups || []).map((lineup) => [
    lineup.team?.name || "Equipo",
    [
      lineup.formation ? `Formación ${lineup.formation}` : "",
      lineup.startXI?.length ? `${lineup.startXI.length} titulares` : "",
    ].filter(Boolean).join(" · ") || "Alineación pendiente",
  ]);
  grid.append(detailBlock("Alineaciones", lineupRows));
  elements.fixtureDetail.append(header, meta, grid);
}

async function loadFootballWidgets() {
  elements.standingsStatus.textContent = "Cargando posiciones...";
  elements.standingsStatus.dataset.kind = "";
  elements.fixturesStatus.textContent = "Cargando partidos...";
  elements.fixturesStatus.dataset.kind = "";
  try {
    const result = await requestJson("/api/widgets/dashboard");
    elements.standingsSeason.textContent = `Temporada ${result.season}`;
    renderStandings(result.standings);
    renderFixtures(result.fixtures, result.minimum_form_matches);
  } catch (error) {
    const message = error.message || "No se pudieron cargar los datos de Liga MX.";
    elements.standingsStatus.textContent = message;
    elements.standingsStatus.dataset.kind = "error";
    elements.fixturesStatus.textContent = message;
    elements.fixturesStatus.dataset.kind = "error";
  }
}

async function loadFixtureDetail(button) {
  const fixtureId = button.dataset.fixtureId;
  button.disabled = true;
  button.textContent = "Cargando...";
  elements.fixtureDetail.replaceChildren(createEmptyState("Consultando detalle del partido..."));
  try {
    const detail = await requestJson(`/api/widgets/fixtures/${encodeURIComponent(fixtureId)}`);
    renderFixtureDetail(detail);
  } catch (error) {
    elements.fixtureDetail.replaceChildren(
      createEmptyState(error.message || "No se pudo cargar el detalle del partido."),
    );
  } finally {
    button.disabled = false;
    button.textContent = "Ver detalle";
  }
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
elements.fixturesList.addEventListener("click", (event) => {
  const button = event.target.closest("[data-fixture-id]");
  if (button && elements.fixturesList.contains(button)) loadFixtureDetail(button);
});

refreshDashboard().catch((error) => {
  setStatus(error.message || "No se pudo cargar el historial.", "error");
});
loadFootballWidgets();
