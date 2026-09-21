"use strict";

const $ = (id) => document.getElementById(id);
const state = { data: null, threshold: 7 };
const percent = (value) => Number.isFinite(value) ? `${(100 * value).toFixed(1).replace(".", ",")} %` : "—";
const ratio = (a, b) => b ? a / b : NaN;
const number = (value, digits = 2) => Number(value).toLocaleString("fr-FR", { maximumFractionDigits: digits });

function classify(results, threshold, positiveLabel, scoreField) {
  const c = { tp: 0, fp: 0, tn: 0, fn: 0 };
  results.forEach((row) => {
    const real = row.label === positiveLabel;
    const detected = row[scoreField] >= threshold;
    if (real && detected) c.tp++; else if (!real && detected) c.fp++; else if (!real) c.tn++; else c.fn++;
  });
  return c;
}

function setScore(name, value) {
  $(name).textContent = percent(value);
  $(`${name}-bar`).style.width = `${Number.isFinite(value) ? value * 100 : 0}%`;
}

function verdict(row, detected, positiveLabel) {
  const real = row.label === positiveLabel;
  if (real && detected) return ["Juste", "good"];
  if (!real && !detected) return ["Juste", "neutral"];
  if (detected) return ["Fausse alerte", "bad"];
  return ["Transit manqué", "bad"];
}

function renderTable(results, threshold, positiveLabel, scoreField) {
  const top = [...results].sort((a, b) => b[scoreField] - a[scoreField]).slice(0, 20);
  $("results-body").innerHTML = top.map((row) => {
    const detected = row[scoreField] >= threshold;
    const [text, kind] = verdict(row, detected, positiveLabel);
    return `<tr>
      <td class="mono">KIC ${row.kepid ?? String(row.row + 1).padStart(4, "0")}</td>
      <td>${row.label === positiveLabel ? "Exoplanète" : "Aucune"}</td>
      <td class="mono">${number(row[scoreField])}</td>
      <td class="mono">${number(row.period_days, 3)} j</td>
      <td class="mono">${number(row.duration_days, 3)} j</td>
      <td><span class="badge ${detected ? "good" : "neutral"}">${detected ? "Détectée" : "Écartée"}</span></td>
      <td><span class="badge ${kind}">${text}</span></td>
    </tr>`;
  }).join("");
}

function drawChart(results, threshold, positiveLabel, scoreField) {
  const canvas = $("snr-chart");
  const dpr = window.devicePixelRatio || 1;
  const width = canvas.clientWidth;
  const height = 300;
  canvas.width = width * dpr; canvas.height = height * dpr;
  const ctx = canvas.getContext("2d"); ctx.scale(dpr, dpr);
  const pad = { l: 45, r: 18, t: 15, b: 35 };
  const chartW = width - pad.l - pad.r, chartH = height - pad.t - pad.b;
  const maxScore = Math.max(threshold + 1, ...results.map((r) => r[scoreField]));
  const step = Math.max(5, Math.ceil(maxScore / 60) * 10);
  const yMax = Math.ceil(maxScore / step) * step;
  ctx.font = "10px ui-monospace, monospace"; ctx.textAlign = "right";
  for (let y = 0; y <= yMax; y += step) {
    const py = pad.t + chartH - (y / yMax) * chartH;
    ctx.strokeStyle = "#e8eaed"; ctx.beginPath(); ctx.moveTo(pad.l, py); ctx.lineTo(width - pad.r, py); ctx.stroke();
    ctx.fillStyle = "#5f6368"; ctx.fillText(String(y), pad.l - 9, py + 3);
  }
  const ty = pad.t + chartH - (threshold / yMax) * chartH;
  ctx.strokeStyle = "#f9ab00"; ctx.setLineDash([5, 5]); ctx.beginPath(); ctx.moveTo(pad.l, ty); ctx.lineTo(width-pad.r, ty); ctx.stroke(); ctx.setLineDash([]);
  ctx.fillStyle = "#b06000"; ctx.textAlign = "left"; ctx.fillText(`seuil ${number(threshold, 1)}`, pad.l + 5, ty - 6);
  results.forEach((row, index) => {
    const x = pad.l + (index / Math.max(1, results.length - 1)) * chartW;
    const y = pad.t + chartH - (Math.min(row[scoreField], yMax) / yMax) * chartH;
    const planet = row.label === positiveLabel;
    ctx.beginPath(); ctx.arc(x, y, planet ? 4 : 1.8, 0, Math.PI * 2);
    ctx.fillStyle = planet ? "#a142f4" : "rgba(26,115,232,.48)"; ctx.fill();
  });
  ctx.fillStyle = "#5f6368"; ctx.textAlign = "center"; ctx.fillText("systèmes →", pad.l + chartW / 2, height - 6);
}

function render() {
  if (!state.data) return;
  const { metadata, results } = state.data;
  const threshold = state.threshold;
  const scoreField = metadata.score_field || "sde";
  const c = classify(results, threshold, metadata.positive_label, scoreField);
  const correct = c.tp + c.tn;
  $("threshold-value").textContent = number(threshold, 1);
  $("systems").textContent = number(results.length, 0);
  $("real-planets").textContent = `${c.tp + c.fn} exoplanètes réelles`;
  $("true-positive").textContent = c.tp;
  $("false-positive").textContent = c.fp;
  $("false-negative").textContent = c.fn;
  $("accuracy-count").textContent = correct;
  $("accuracy-rate").textContent = `${percent(ratio(correct, results.length))} du total`;
  [["tp", c.tp], ["fp", c.fp], ["tn", c.tn], ["fn", c.fn]].forEach(([key, value]) => $(`matrix-${key}`).textContent = value);
  setScore("precision", ratio(c.tp, c.tp + c.fp));
  setScore("recall", ratio(c.tp, c.tp + c.fn));
  setScore("specificity", ratio(c.tn, c.tn + c.fp));
  renderTable(results, threshold, metadata.positive_label, scoreField);
  drawChart(results, threshold, metadata.positive_label, scoreField);
}

async function load() {
  try {
    const response = await fetch("results.json", { cache: "no-store" });
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    state.data = await response.json();
    const { metadata, results } = state.data;
    const scoreField = metadata.score_field || "sde";
    state.threshold = metadata.default_threshold;
    $("threshold").value = state.threshold;
    $("threshold").max = Math.max(30, Math.ceil(Math.max(...results.map((r) => r[scoreField]))));
    $("dataset-name").textContent = metadata.dataset;
    $("status-dot").classList.add("ready");
    $("analysis-meta").textContent = `${number(metadata.periods_tested, 0)} périodes · ${number(metadata.elapsed_seconds, 1)} s de calcul`;
    $("generated-at").textContent = `Analyse du ${new Date(metadata.generated_at).toLocaleString("fr-FR")}`;
    render();
  } catch (error) {
    $("status-dot").classList.add("error");
    $("dataset-name").textContent = "results.json indisponible";
    document.querySelector("main").insertAdjacentHTML("beforeend", `<p class="error-message">Impossible de charger les résultats. Lancez d'abord <code>python3 -m script.evaluate</code>, puis servez le dossier avec <code>python3 web/server.py</code>.</p>`);
  }
}

$("threshold").addEventListener("input", (event) => { state.threshold = Number(event.target.value); render(); });
window.addEventListener("resize", () => state.data && drawChart(state.data.results, state.threshold, state.data.metadata.positive_label, state.data.metadata.score_field || "sde"));
load();
