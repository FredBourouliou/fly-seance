// The séance page: one EventSource per question, the ritual shown as it arrives.
// Everything the fly's body does is driven by the measured firing rates.

const $ = (id) => document.getElementById(id);
const reducedMotion = matchMedia("(prefers-reduced-motion: reduce)").matches;

const READOUTS = [
  { id: "MN9", moves: "proboscis", voice: "feed" },
  { id: "aBN1", moves: "antennal grooming", voice: "groom" },
  { id: "DN1", moves: "antennal grooming", voice: "groom" },
  { id: "DN2", moves: "antennal grooming", voice: "groom" },
];
// Each offering is a thing the medium sets down, and a sense the fly receives it with.
const GIFTS = [
  { kind: "nectar", thing: "a grain of sugar", label: "Sugar", sense: "tasted by its mouth",
    neurons: "sugar receptors", watch: "mouth" },
  { kind: "bitter", thing: "a sprig of wormwood", label: "Wormwood", sense: "tasted, and bitter",
    neurons: "bitter receptors", watch: "mouth" },
  { kind: "touch", thing: "a feather against its antenna", label: "Feather", sense: "felt on its antenna",
    neurons: "antennal touch neurons", watch: "front legs" },
  { kind: "breath", thing: "a breath of candle smoke", label: "Smoke", sense: "stirs its antenna",
    neurons: "JON-F antennal neurons", watch: "front legs" },
];
const SVG = "http://www.w3.org/2000/svg";
const VOICE_MARK = { feed: "F", groom: "G", still: "·" };
const VOICE_WORD = { feed: "fed", groom: "groomed", still: "stayed still" };
// The answer is read by code from the verdict, never by the model.
const ANSWER = { feed: "Yes.", still: "No.", groom: "It will not say." };
const HELPLINES = "https://findahelpline.com/";
let veiled = false;
let busy = false;
let lastAnswerAt = 0;
const METER_MAX_HZ = 120;
const K = 5;

let fly = null;
let source = null;
let thresholds = { feed: 10.5, groom: 13 };
let received = [];
let verdictVoice = "still";

// ---------- the fly ----------

async function wakeFly() {
  try {
    const { createFly } = await import("./fly/fly.js");
    fly = await createFly($("fly"), { reducedMotion });
  } catch (err) {
    console.error(err);
    const p = $("stage-fallback");
    p.textContent = "The fly's body could not be shown here. The séance still runs; its answer is written below.";
    p.hidden = false;
  }
}

/** Drive from rates: a movement only plays if its neurons crossed their threshold. */
function driveFrom(rates) {
  const groomHz = Math.max(rates.aBN1, rates.DN1, rates.DN2);
  return {
    feed: rates.MN9 >= thresholds.feed ? Math.min(rates.MN9 / 100, 1) : 0,
    groom: groomHz >= thresholds.groom ? Math.min(groomHz / 80, 1) : 0,
  };
}

function setDrive(d) {
  fly?.setDrive(d);
  const parts = [];
  if (d.feed > 0) parts.push("extends its proboscis");
  if (d.groom > 0) parts.push("grooms its antennae");
  $("fly-state").textContent = parts.length ? `The fly ${parts.join(" and ")}.` : "The fly is still.";
}

// ---------- sittings ----------

function roman(n) {
  const map = [[1000, "M"], [900, "CM"], [500, "D"], [400, "CD"], [100, "C"], [90, "XC"],
    [50, "L"], [40, "XL"], [10, "X"], [9, "IX"], [5, "V"], [4, "IV"], [1, "I"]];
  let out = "";
  for (const [v, s] of map) while (n >= v) { out += s; n -= v; }
  return out;
}
function sitting(advance) {
  let n = 1;
  try {
    n = Number(localStorage.getItem("fly-seance-sitting") || "1");
    if (advance) localStorage.setItem("fly-seance-sitting", String(++n));
  } catch { /* storage unavailable: stay at the first sitting */ }
  $("sitting-n").textContent = roman(n);
}

// ---------- the offering ----------

function engraving(kind) {
  const svg = document.createElementNS(SVG, "svg");
  svg.setAttribute("class", "engraving");
  svg.dataset.kind = kind;
  svg.setAttribute("aria-hidden", "true");
  const use = document.createElementNS(SVG, "use");
  use.setAttribute("href", `#gift-${kind}`);
  svg.append(use);
  return svg;
}

const listed = (items) => items.length < 2 ? items.join("")
  : `${items.slice(0, -1).join(", ")} and ${items.at(-1)}`;

function showOffering(offering) {
  const given = GIFTS.filter((g) => offering.rates[g.kind] > 0);
  const watch = [...new Set(given.map((g) => g.watch))];
  $("offer-line").textContent = given.length
    ? `The medium sets down ${listed(given.map((g) => g.thing))}. Watch its ${listed(watch)}.`
    : "The medium sets down nothing. The fly is left alone.";

  const list = $("gifts");
  list.replaceChildren();
  for (const g of GIFTS) {
    const hz = offering.rates[g.kind];
    const li = document.createElement("li");
    li.className = "gift";
    li.dataset.kind = g.kind;
    const name = document.createElement("p");
    name.className = "gift-name";
    name.textContent = g.label;
    const sense = document.createElement("p");
    sense.className = "gift-sense";
    sense.textContent = hz > 0 ? g.sense : "not offered";
    const bar = document.createElement("div");
    bar.className = "gift-bar";
    bar.append(document.createElement("i"));
    const dose = document.createElement("p");
    dose.className = "gift-dose";
    dose.textContent = hz > 0 ? `${hz} Hz · ${g.neurons}` : "";
    li.append(engraving(g.kind), name, sense, bar, dose);
    list.append(li);
    requestAnimationFrame(() => {
      if (hz > 0) li.classList.add("is-given");
      bar.firstChild.style.transform = `scaleX(${hz / 250})`;
    });
  }

  // The same things, laid on the table beside the fly's head.
  const laid = $("laid");
  laid.replaceChildren(...given.map((g) => {
    const e = engraving(g.kind);
    if (g.watch === "front legs") e.classList.add("is-raised");
    return e;
  }));
  laid.hidden = given.length === 0;
  laid.classList.remove("is-shown");
  requestAnimationFrame(() => laid.classList.add("is-shown"));

  $("veil").hidden = !offering.veil;
  veiled = offering.veil;
  $("why").textContent = offering.why ? `The medium heard: ${offering.why}` : "";
  $("offering").hidden = false;
}

// ---------- trials, raster, rates ----------

function resetProof() {
  received = [];
  const ol = $("trials");
  ol.replaceChildren();
  for (let i = 0; i < K; i++) {
    const li = document.createElement("li");
    li.className = "trial is-running";
    li.textContent = String(i + 1);
    li.setAttribute("aria-label", `Trial ${i + 1}: running`);
    ol.append(li);
  }
  $("plain").textContent = "";
  renderRates({ MN9: 0, aBN1: 0, DN1: 0, DN2: 0 });
  clearRaster();
  $("proof-empty").hidden = true;
  $("proof-body").hidden = false;
}

function showTrial(t) {
  received.push(t);
  const li = $("trials").children[t.i];
  li.classList.remove("is-running");
  li.dataset.voice = t.voice;
  li.textContent = VOICE_MARK[t.voice];
  li.setAttribute("aria-label", `Trial ${t.i + 1}: the fly ${VOICE_WORD[t.voice]}`);
  const mean = meanRates(received);
  renderRates(mean);
  setDrive(driveFrom(mean));
  drawRaster(t);
}

function meanRates(trials) {
  const out = {};
  for (const r of READOUTS) out[r.id] = trials.reduce((s, t) => s + t.rates_hz[r.id], 0) / trials.length;
  return out;
}

function renderRates(rates) {
  const body = $("rates");
  body.replaceChildren();
  for (const r of READOUTS) {
    const hz = rates[r.id];
    const th = thresholds[r.voice];
    const tr = document.createElement("tr");
    const name = document.createElement("th");
    name.scope = "row";
    name.textContent = r.id;
    const moves = document.createElement("td");
    moves.textContent = r.moves;
    const num = document.createElement("td");
    num.className = "num";
    num.textContent = hz.toFixed(1);
    const cell = document.createElement("td");
    const meter = document.createElement("div");
    meter.className = "meter";
    meter.dataset.voice = r.voice;
    meter.classList.toggle("is-over", hz >= th);
    meter.setAttribute("role", "img");
    meter.setAttribute("aria-label", `${hz.toFixed(1)} Hz, threshold ${th} Hz, ${hz >= th ? "above" : "below"}`);
    const fill = document.createElement("i");
    fill.style.transform = `scaleX(${Math.min(hz / METER_MAX_HZ, 1)})`;
    const mark = document.createElement("b");
    mark.style.left = `${(th / METER_MAX_HZ) * 100}%`;
    meter.append(fill, mark);
    cell.append(meter);
    tr.append(name, moves, num, cell);
    body.append(tr);
  }
}

function cssColor(name) {
  return getComputedStyle(document.documentElement).getPropertyValue(name).trim();
}

let rasterAnim = 0;
function clearRaster() {
  cancelAnimationFrame(rasterAnim);
  const c = $("raster");
  const ctx = c.getContext("2d");
  sizeCanvas(c);
  ctx.clearRect(0, 0, c.width, c.height);
}
function sizeCanvas(c) {
  const dpr = devicePixelRatio || 1;
  c.width = Math.round(c.clientWidth * dpr);
  c.height = Math.round(c.clientHeight * dpr);
}

function drawRaster(t) {
  cancelAnimationFrame(rasterAnim);
  const c = $("raster");
  sizeCanvas(c);
  const ctx = c.getContext("2d");
  const rows = t.raster_rows;
  const kind = rows.map((r) => r.startsWith("readout:") ? "read" : r.startsWith("offering:") ? "offer" : "other");
  const colors = { read: cssColor("--candle"), offer: cssColor("--ink"), other: cssColor("--ink-faint") };
  const rowH = c.height / rows.length;
  const tick = Math.max(1, Math.round(c.width / 500));
  const h = Math.max(1, rowH * (rowH > 3 ? 0.7 : 1));
  const spikes = t.raster; // [row, t in s], sorted by time
  const paintUpTo = (sec, from) => {
    let i = from;
    for (; i < spikes.length && spikes[i][1] <= sec; i++) {
      const [row, ts] = spikes[i];
      const k = kind[row];
      ctx.globalAlpha = k === "other" ? 0.55 : 1;
      ctx.fillStyle = colors[k];
      ctx.fillRect(ts * c.width, row * rowH, k === "read" ? tick * 2 : tick, k === "read" ? Math.max(h, 3) : h);
    }
    return i;
  };
  ctx.clearRect(0, 0, c.width, c.height);
  if (reducedMotion) { paintUpTo(1, 0); return; }
  const start = performance.now();
  let drawn = 0;
  const step = (now) => {
    const sec = Math.min((now - start) / 1200, 1);
    drawn = paintUpTo(sec, drawn);
    if (sec < 1) rasterAnim = requestAnimationFrame(step);
  };
  rasterAnim = requestAnimationFrame(step);
}

// ---------- questions the spirits refuse ----------

function showRefusal(r) {
  const p = $("refusal");
  p.replaceChildren();
  const [before, after] = r.message.split("findahelpline.com");
  p.append(before);
  if (after !== undefined) {
    const a = document.createElement("a");
    a.href = HELPLINES;
    a.target = "_blank";
    a.rel = "noopener";
    a.textContent = "findahelpline.com";
    p.append(a, after);
  }
  p.hidden = false;
  $("proof-empty").hidden = false;
  $("proof-body").hidden = true;
}

// ---------- the ritual ----------

function setBusy(value) {
  busy = value;
  if (!value) lastAnswerAt = performance.now();
  $("q").disabled = busy;
  $("ask-btn").disabled = busy;
  $("ask-btn").textContent = busy ? "Listening" : "Ask";
  for (const b of document.querySelectorAll(".example")) b.disabled = busy;
}

function fail(message) {
  const p = $("failure");
  p.textContent = message;
  p.hidden = false;
}

function ask(question) {
  question = question.trim();
  if (!question) { fail("Ask the fly a question."); $("q").focus(); return; }
  source?.close();
  $("failure").hidden = true;
  $("voice").textContent = "";
  delete $("voice").dataset.voice;
  $("answer-block").hidden = true;
  $("refusal").hidden = true;
  $("offering").hidden = true;
  $("laid").hidden = true;
  const quote = $("question-quote");
  quote.textContent = question;
  quote.hidden = false;
  setDrive({ feed: 0, groom: 0 });
  document.querySelector(".masthead").scrollIntoView({ behavior: reducedMotion ? "auto" : "smooth" });
  setBusy(true);
  sitting(true);

  let finished = false;
  source = new EventSource(`/api/seance?q=${encodeURIComponent(question)}`);
  const on = (name, fn) => source.addEventListener(name, (e) => fn(JSON.parse(e.data)));

  on("offering", (o) => { showOffering(o); resetProof(); });
  on("refusal", (r) => showRefusal(r));
  on("trial", showTrial);
  on("verdict", (v) => {
    thresholds = v.thresholds_hz;
    verdictVoice = v.voice;
    renderRates(v.mean_rates_hz);
    setDrive(driveFrom(v.mean_rates_hz));
  });
  on("voice", (v) => {
    const el = $("voice");
    el.dataset.voice = verdictVoice;
    const answer = $("answer");
    // Behind the veil, stillness is silence rather than a no: the same verdict, said gently.
    answer.textContent = veiled && verdictVoice === "still" ? "Silence." : ANSWER[verdictVoice];
    answer.dataset.voice = verdictVoice;
    $("answer-block").hidden = false;
    el.textContent = v.text || "The medium is silent, but the body has answered.";
    $("plain").textContent = v.plain;
  });
  on("done", () => { finished = true; source.close(); setBusy(false); $("q").select(); });
  on("failure", (f) => {
    finished = true;
    source.close();
    setBusy(false);
    fail(f.message);
    if (f.kind !== "busy") $("question-quote").hidden = true;
  });
  source.onerror = () => {
    if (finished) return;
    source.close();
    setBusy(false);
    fail("The séance server is not answering. Is python -m fly_seance.server running?");
  };
}

// ---------- between questions ----------
// The room sends the real brain a small random stimulus now and then; the
// connectome alone decides whether the body moves. Nothing here is scripted.

const DRIFT_MIN_MS = 15000, DRIFT_MAX_MS = 40000, DRIFT_HOLD_MS = 5000, AFTER_ANSWER_MS = 30000;
const DRIFT_ACT = { feed: "It reaches for it.", groom: "It grooms its antennae.", still: "It does not stir." };
let driftTimer = 0;

function scheduleDrift() {
  clearTimeout(driftTimer);
  driftTimer = setTimeout(drift, DRIFT_MIN_MS + Math.random() * (DRIFT_MAX_MS - DRIFT_MIN_MS));
}

async function drift() {
  const quiet = !busy && !document.hidden && performance.now() - lastAnswerAt > AFTER_ANSWER_MS;
  if (!quiet) return scheduleDrift();
  try {
    const res = await fetch("/api/drift");
    if (!res.ok || busy) return scheduleDrift();
    const d = await res.json();
    const caption = $("drift");
    caption.textContent = `${d.what} (${d.stimulus}, ${d.rate_hz} Hz). ${DRIFT_ACT[d.voice]}`;
    caption.classList.add("is-shown");
    setDrive(driveFrom(d.rates_hz));
    setTimeout(() => {
      caption.classList.remove("is-shown");
      if (!busy && performance.now() - lastAnswerAt > AFTER_ANSWER_MS) setDrive({ feed: 0, groom: 0 });
    }, DRIFT_HOLD_MS);
  } catch { /* server away: try again later */ }
  scheduleDrift();
}

// ---------- wiring ----------

$("ask").addEventListener("submit", (e) => { e.preventDefault(); ask($("q").value); });
for (const b of document.querySelectorAll(".example")) {
  b.addEventListener("click", () => { $("q").value = b.textContent; ask(b.textContent); });
}
addEventListener("resize", () => { if (received.length) drawRaster(received[received.length - 1]); });

sitting(false);
wakeFly();
lastAnswerAt = -AFTER_ANSWER_MS;
scheduleDrift();
