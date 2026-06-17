const state = {
  eventSeq: 100,
  ws: null,
  matchId: null,
  matches: [],
  selectedMatch: null,
  externalMatches: [],
  externalOdds: [],
};

const els = {
  selectedMatchTitle: document.querySelector("#selected-match-title"),
  matchSelect: document.querySelector("#match-select"),
  matchMeta: document.querySelector("#match-meta"),
  scoreHomeTeam: document.querySelector("#score-home-team"),
  scoreAwayTeam: document.querySelector("#score-away-team"),
  runtimePill: document.querySelector("#runtime-pill"),
  metricEvents: document.querySelector("#metric-events"),
  metricPredictions: document.querySelector("#metric-predictions"),
  metricBus: document.querySelector("#metric-bus"),
  metricWs: document.querySelector("#metric-ws"),
  predictionVersion: document.querySelector("#prediction-version"),
  homeWinLabel: document.querySelector("#home-win-label"),
  drawLabel: document.querySelector("#draw-label"),
  awayWinLabel: document.querySelector("#away-win-label"),
  homeWinBar: document.querySelector("#home-win-bar"),
  drawBar: document.querySelector("#draw-bar"),
  awayWinBar: document.querySelector("#away-win-bar"),
  modelStrip: document.querySelector("#model-strip"),
  matchStatus: document.querySelector("#match-status"),
  homeScore: document.querySelector("#home-score"),
  awayScore: document.querySelector("#away-score"),
  matchClock: document.querySelector("#match-clock"),
  matchPeriod: document.querySelector("#match-period"),
  homeShots: document.querySelector("#home-shots"),
  awayShots: document.querySelector("#away-shots"),
  homeXg: document.querySelector("#home-xg"),
  awayXg: document.querySelector("#away-xg"),
  pressureHome: document.querySelector("#pressure-home"),
  pressureAway: document.querySelector("#pressure-away"),
  qualityScore: document.querySelector("#quality-score"),
  qualityWarnings: document.querySelector("#quality-warnings"),
  simulationRuns: document.querySelector("#simulation-runs"),
  simulationList: document.querySelector("#simulation-list"),
  eventLog: document.querySelector("#event-log"),
  historyCount: document.querySelector("#history-count"),
  predictionHistory: document.querySelector("#prediction-history"),
  auditCount: document.querySelector("#audit-count"),
  qualityHistory: document.querySelector("#quality-history"),
  lotteryNote: document.querySelector("#lottery-note"),
  pushStatus: document.querySelector("#push-status"),
  externalStatus: document.querySelector("#external-status"),
  externalMatchList: document.querySelector("#external-match-list"),
  externalOddsList: document.querySelector("#external-odds-list"),
};

function percent(value) {
  return `${Math.round((value || 0) * 1000) / 10}%`;
}

function formatClock(seconds) {
  const mins = Math.floor((seconds || 0) / 60);
  const secs = Math.floor((seconds || 0) % 60);
  return `${String(mins).padStart(2, "0")}:${String(secs).padStart(2, "0")}`;
}

function formatDateTime(value) {
  if (!value) {
    return "--";
  }
  return new Date(value).toLocaleString("zh-CN", { hour12: false });
}

async function fetchJson(url, options) {
  const response = await fetch(url, options);
  if (!response.ok) {
    throw new Error(`${response.status} ${response.statusText}`);
  }
  return response.json();
}

function setProbability(prediction) {
  els.predictionVersion.textContent = prediction.source_prediction_version_id
    ? prediction.source_prediction_version_id.slice(0, 11)
    : prediction.settlement_status;
  const home = prediction.outcomes.find((item) => item.code === "home_win");
  const draw = prediction.outcomes.find((item) => item.code === "draw");
  const away = prediction.outcomes.find((item) => item.code === "away_win");
  els.homeWinLabel.textContent = `${percent(home.probability)} / ${home.fair_decimal_odds}`;
  els.drawLabel.textContent = `${percent(draw.probability)} / ${draw.fair_decimal_odds}`;
  els.awayWinLabel.textContent = `${percent(away.probability)} / ${away.fair_decimal_odds}`;
  els.homeWinBar.style.width = percent(home.probability);
  els.drawBar.style.width = percent(draw.probability);
  els.awayWinBar.style.width = percent(away.probability);
  els.lotteryNote.textContent = prediction.note;
}

function setModelStrip(models) {
  els.modelStrip.innerHTML = models
    .map(
      (model) => `
        <div class="model-chip">
          <span>${model.model_name}</span>
          <strong>${percent(model.weight)}</strong>
        </div>
      `,
    )
    .join("");
}

function clearPrediction() {
  els.predictionVersion.textContent = "等待事件";
  els.homeWinLabel.textContent = "--";
  els.drawLabel.textContent = "--";
  els.awayWinLabel.textContent = "--";
  els.homeWinBar.style.width = "0%";
  els.drawBar.style.width = "0%";
  els.awayWinBar.style.width = "0%";
  els.modelStrip.innerHTML = "";
}

function setRuntime(status) {
  els.runtimePill.textContent = status.status;
  els.metricEvents.textContent = status.event_count;
  els.metricPredictions.textContent = status.prediction_count;
  els.metricBus.textContent = status.bus_message_count;
  els.metricWs.textContent = status.active_ws_connections;
}

function setMatchState(matchState) {
  els.matchStatus.textContent = matchState.status;
  els.homeScore.textContent = matchState.home.score;
  els.awayScore.textContent = matchState.away.score;
  els.matchClock.textContent = formatClock(matchState.match_clock_sec);
  els.matchPeriod.textContent = `P${matchState.period}`;
  els.homeShots.textContent = matchState.home.shots;
  els.awayShots.textContent = matchState.away.shots;
  els.homeXg.textContent = matchState.home.xg.toFixed(2);
  els.awayXg.textContent = matchState.away.xg.toFixed(2);

  const totalXg = Math.max(0.1, matchState.home.xg + matchState.away.xg);
  const homeWidth = Math.max(18, Math.min(82, (matchState.home.xg / totalXg) * 100));
  els.pressureHome.style.width = `${homeWidth}%`;
  els.pressureAway.style.width = `${100 - homeWidth}%`;
}

function setMatchMeta(match) {
  state.selectedMatch = match;
  const score =
    match.home_score === null || match.away_score === null
      ? "vs"
      : `${match.home_score} - ${match.away_score}`;
  const kickoff = new Date(match.kickoff_time_utc).toLocaleString("zh-CN", { hour12: false });
  els.selectedMatchTitle.textContent = `${match.home_team_name} ${score} ${match.away_team_name}`;
  els.scoreHomeTeam.textContent = match.home_team_name;
  els.scoreAwayTeam.textContent = match.away_team_name;
  els.matchMeta.innerHTML = `
    <strong>${match.stage} / Group ${match.group} / Match ${match.match_no}</strong>
    <span>${kickoff} UTC / ${match.venue} / ${match.city} / ${match.status}</span>
  `;
}

function setSimulation(simulation) {
  els.simulationRuns.textContent = `${simulation.runs} runs`;
  els.simulationList.innerHTML = simulation.teams
    .slice(0, 4)
    .map(
      (team) => `
        <div class="simulation-row">
          <div>
            <strong>${team.team_id}</strong>
            <span>晋级 ${percent(team.group_advance_prob)} / 冠军 ${percent(team.champion_prob)}</span>
          </div>
          <strong>${percent(team.final_prob)}</strong>
        </div>
      `,
    )
    .join("");
}

function setQuality(quality) {
  els.qualityScore.textContent = `质量 ${percent(quality.score)}`;
  els.qualityWarnings.textContent = quality.warnings.length ? quality.warnings.join(", ") : "通过";
}

function addLog(kind, text, detail) {
  const item = document.createElement("li");
  const time = new Date().toLocaleTimeString("zh-CN", { hour12: false });
  item.innerHTML = `<span>${time}</span><strong>${kind}</strong><span>${text} ${detail || ""}</span>`;
  els.eventLog.prepend(item);
  while (els.eventLog.children.length > 12) {
    els.eventLog.removeChild(els.eventLog.lastChild);
  }
}

function renderEventLog(events) {
  if (!events.length) {
    els.eventLog.innerHTML = '<li><span>--</span><strong>system</strong><span>等待事件接入</span></li>';
    return;
  }

  els.eventLog.innerHTML = events
    .slice(0, 12)
    .map((event) => {
      const time = new Date(event.received_at).toLocaleTimeString("zh-CN", { hour12: false });
      return `
        <li>
          <span>${time}</span>
          <strong>${event.event_type}</strong>
          <span>${event.event_id} accepted=${event.accepted}</span>
        </li>
      `;
    })
    .join("");
}

function renderQualityHistory(events) {
  els.auditCount.textContent = `${events.length} events`;
  if (!events.length) {
    els.qualityHistory.innerHTML = '<p class="empty">暂无质量审计记录</p>';
    return;
  }

  els.qualityHistory.innerHTML = events
    .map((event) => {
      const warningText = event.warnings.length ? event.warnings.join(", ") : "pass";
      return `
        <div class="quality-item">
          <span>${event.event_type}</span>
          <div>
            <strong>${event.event_id}</strong>
            <span>${event.source} / ${warningText}</span>
          </div>
          <span class="quality-score">${percent(event.score)}</span>
        </div>
      `;
    })
    .join("");
}

function renderPredictionHistory(predictions) {
  els.historyCount.textContent = `${predictions.length} items`;
  if (!predictions.length) {
    els.predictionHistory.innerHTML = '<p class="empty">暂无预测历史</p>';
    return;
  }

  els.predictionHistory.innerHTML = predictions
    .map(
      (prediction) => `
        <div class="history-item">
          <span>${new Date(prediction.generated_at).toLocaleTimeString("zh-CN", { hour12: false })}</span>
          <div>
            <strong>${prediction.prediction_version_id.slice(0, 11)}</strong>
            <span>confidence ${percent(prediction.confidence_level)}</span>
          </div>
          <div class="history-bars">
            <div class="tiny-track"><div class="home" style="width:${percent(prediction.home_win)}"></div></div>
            <div class="tiny-track"><div class="draw" style="width:${percent(prediction.draw)}"></div></div>
            <div class="tiny-track"><div class="away" style="width:${percent(prediction.away_win)}"></div></div>
          </div>
        </div>
      `,
    )
    .join("");
}

function renderExternalMatches(matches) {
  if (!els.externalMatchList) {
    return;
  }
  state.externalMatches = matches;
  if (!matches.length) {
    els.externalMatchList.innerHTML = '<p class="empty">暂无外部赛程更新</p>';
    return;
  }

  els.externalMatchList.innerHTML = matches
    .slice(0, 12)
    .map((match) => {
      const score =
        match.home_score === null || match.away_score === null
          ? "vs"
          : `${match.home_score}-${match.away_score}`;
      return `
        <button class="external-match-row" data-external-match="${match.match_id}" type="button">
          <span>${match.match_id}</span>
          <strong>${score}</strong>
          <span>${match.status}</span>
          <span>${formatDateTime(match.kickoff_time_utc)}</span>
        </button>
      `;
    })
    .join("");

  els.externalMatchList.querySelectorAll("[data-external-match]").forEach((button) => {
    button.addEventListener("click", () => setSelectedMatch(button.dataset.externalMatch));
  });
}

function renderExternalOdds(oddsUpdates) {
  if (!els.externalOddsList) {
    return;
  }
  state.externalOdds = oddsUpdates;
  if (!oddsUpdates.length) {
    els.externalOddsList.innerHTML = '<p class="empty">当前比赛暂无映射后的竞彩赔率</p>';
    return;
  }

  els.externalOddsList.innerHTML = oddsUpdates
    .map((update) => {
      const selections = update.selections
        .map(
          (selection) => `
            <div>
              <span>${selection.outcome}</span>
              <strong>${selection.decimal_odds.toFixed(2)}</strong>
            </div>
          `,
        )
        .join("");
      const handicap = update.handicap === null ? "" : ` / 让球 ${update.handicap}`;
      return `
        <div class="external-odds-card">
          <div class="external-odds-head">
            <strong>${update.market}${handicap}</strong>
            <span>${formatDateTime(update.observed_at)}</span>
          </div>
          <div class="external-odds-grid">${selections}</div>
        </div>
      `;
    })
    .join("");
}

async function refreshAll() {
  if (!state.matchId) {
    return;
  }

  const runtime = await fetchJson("/api/v1/runtime/status");
  setRuntime(runtime);

  try {
    const lottery = await fetchJson(`/api/v1/matches/${state.matchId}/lottery-analysis`);
    setProbability(lottery);
  } catch (error) {
    clearPrediction();
    addLog("prediction", "等待首个预测", "");
  }

  try {
    const matchState = await fetchJson(`/api/v1/matches/${state.matchId}/state`);
    setMatchState(matchState);
  } catch (error) {
    addLog("state", "等待首个比赛状态", "");
  }

  const simulation = await fetchJson("/api/v1/tournament/simulation/latest");
  setSimulation(simulation);

  const events = await fetchJson("/api/v1/events/recent?limit=20");
  renderEventLog(events);
  renderQualityHistory(events);

  const predictions = await fetchJson(`/api/v1/matches/${state.matchId}/predictions/recent?limit=20`);
  renderPredictionHistory(predictions);
  if (predictions[0]) {
    setModelStrip(predictions[0].models);
  }

  const externalMatches = await fetchJson("/api/v1/external/matches");
  renderExternalMatches(externalMatches);
  const externalOdds = await fetchJson(`/api/v1/external/odds?match_id=${state.matchId}`);
  renderExternalOdds(externalOdds);
  if (els.externalStatus) {
    els.externalStatus.textContent = `${externalMatches.length} schedule / ${externalOdds.length} odds`;
  }
}

async function syncExternalData() {
  if (els.externalStatus) {
    els.externalStatus.textContent = "syncing";
  }
  const result = await fetchJson("/api/v1/external/refresh", { method: "POST" });
  addLog(
    "external",
    `schedule=${result.schedule_updates}`,
    `odds=${result.odds_updates}`,
  );
  await loadMatches();
}

function buildEvent(type) {
  state.eventSeq += 1;
  const now = new Date();
  const clock = 900 + state.eventSeq * 15;
  const base = {
    event_id: `ui_evt_${Date.now()}_${state.eventSeq}`,
    match_id: state.matchId,
    event_time: now.toISOString(),
    ingest_time: now.toISOString(),
    period: 1,
    match_clock_sec: clock,
    source: "ui",
    confidence_score: 0.99,
    correction_flag: false,
    payload: {},
  };

  if (type === "shot_home") {
    return {
      ...base,
      event_type: "shot",
      team_id: "home",
      player_id: "home_attacker",
      x: 84,
      y: 48,
      payload: { xg: 0.12, side: "home" },
    };
  }
  if (type === "shot_away") {
    return {
      ...base,
      event_type: "shot",
      team_id: "away",
      player_id: "away_attacker",
      x: 18,
      y: 52,
      payload: { xg: 0.10, side: "away" },
    };
  }
  if (type === "goal_home") {
    return {
      ...base,
      event_type: "goal",
      team_id: "home",
      player_id: "home_attacker",
      x: 92,
      y: 50,
      payload: { side: "home" },
    };
  }
  return {
    ...base,
    event_type: "red_card",
    team_id: "away",
    player_id: "away_defender",
    x: 42,
    y: 38,
    payload: { side: "away" },
  };
}

async function sendEvent(type) {
  const event = buildEvent(type);
  const response = await fetchJson("/api/v1/events", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(event),
  });
  setQuality(response.data_quality);
  addLog(event.event_type, event.event_id, `accepted=${response.accepted}`);
  await refreshAll();
}

function connectPush() {
  if (state.ws && state.ws.readyState === WebSocket.OPEN) {
    return;
  }
  const protocol = window.location.protocol === "https:" ? "wss" : "ws";
  state.ws = new WebSocket(`${protocol}://${window.location.host}/api/v1/ws/predictions`);
  state.ws.addEventListener("open", () => {
    els.pushStatus.textContent = "已连接";
    els.pushStatus.classList.remove("muted");
    state.ws.send(JSON.stringify({ action: "subscribe", match_ids: [state.matchId] }));
    addLog("push", "订阅实时预测", state.matchId);
  });
  state.ws.addEventListener("message", (event) => {
    const data = JSON.parse(event.data);
    if (data.type === "prediction_update") {
      addLog("push", "收到预测更新", data.prediction_version_id.slice(0, 11));
      refreshAll();
    }
  });
  state.ws.addEventListener("close", () => {
    els.pushStatus.textContent = "未连接";
    els.pushStatus.classList.add("muted");
  });
}

function switchView(view) {
  document.querySelectorAll(".nav-item").forEach((button) => {
    button.classList.toggle("active", button.dataset.view === view);
  });

  document.querySelectorAll("[data-views]").forEach((panel) => {
    const views = panel.dataset.views.split(" ");
    panel.classList.toggle("is-hidden", !views.includes(view));
  });
}

async function loadMatches() {
  state.matches = await fetchJson("/api/v1/worldcup/matches");
  els.matchSelect.innerHTML = state.matches
    .map((match) => {
      const score =
        match.home_score === null || match.away_score === null
          ? "vs"
          : `${match.home_score}-${match.away_score}`;
      return `
        <option value="${match.match_id}">
          #${match.match_no} ${match.home_team_name} ${score} ${match.away_team_name} (${match.status})
        </option>
      `;
    })
    .join("");

  const firstOpen = state.matches.find((match) => match.status !== "finished") || state.matches[0];
  setSelectedMatch(firstOpen.match_id);
}

function setSelectedMatch(matchId) {
  state.matchId = matchId;
  const match = state.matches.find((item) => item.match_id === matchId);
  if (match) {
    els.matchSelect.value = matchId;
    setMatchMeta(match);
  }
  clearPrediction();
  refreshAll();
}

document.querySelector("#btn-refresh").addEventListener("click", refreshAll);
document.querySelector("#btn-external-refresh").addEventListener("click", syncExternalData);
document.querySelector("#btn-connect").addEventListener("click", connectPush);
els.matchSelect.addEventListener("change", () => setSelectedMatch(els.matchSelect.value));
document.querySelectorAll("[data-event]").forEach((button) => {
  button.addEventListener("click", () => sendEvent(button.dataset.event));
});
document.querySelectorAll(".nav-item").forEach((button) => {
  button.addEventListener("click", () => switchView(button.dataset.view));
});

els.eventLog.innerHTML = '<li><span>--</span><strong>system</strong><span>等待事件接入</span></li>';
switchView("live");
loadMatches();
