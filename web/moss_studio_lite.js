// MOSS-Image Studio Lite - SatoDive: a small panel under MOSS Generate Lite (no reference pictures).
// Every setting stays a native, visible widget; the panel only adds what widgets cannot do: the Layout canvas
// (draws the `layout` widget: boxes and a strict strength per box), the Enhance button
// (a separate small job + review before Apply; with boxes each box is rewritten on its own) and the last report.
// The node grows when the panel needs more room (never shrinks a size you chose), so nothing is ever hidden.
// Without this file the node still works: `layout` is then plain JSON text.
import { app } from "../../scripts/app.js";
import { api } from "../../scripts/api.js";

const GEN = "MOSSGenerateLite_SatoDive";
const ENH = "MOSSPromptEnhancerLite_SatoDive";
const MODES = ["auto (official choice)", "caption", "layout"];
const DETAIL = ["official (220-500 words)", "short (80-150 words)", "minimal (as short as my brief)"];
const TYPES = { object: "#4fb3ff", character: "#ff9f43", text: "#3ccf91" };

// ------------------------------------------------------------------------------------------- tiny DOM kit
function h(tag, props, ...kids) {
  const [name, ...cls] = tag.split(".");
  const el = document.createElement(name || "div");
  if (cls.length) el.className = cls.join(" ");
  for (const [k, v] of Object.entries(props || {})) {
    if (v == null || v === false) continue;
    if (k === "on") for (const [ev, fn] of Object.entries(v)) el.addEventListener(ev, fn);
    else if (k === "style") { for (const [sk, sv] of Object.entries(v)) { if (sv == null) continue; if (sk.startsWith("--")) el.style.setProperty(sk, sv); else el.style[sk] = sv; } }
    else if (k in el) el[k] = v;
    else el.setAttribute(k, v === true ? "" : v);
  }
  for (const c of kids.flat(9)) if (c != null && c !== false) el.appendChild(c instanceof Node ? c : document.createTextNode(String(c)));
  return el;
}
const put = (el, ...kids) => { el.replaceChildren(); for (const c of kids.flat(9)) if (c != null && c !== false) el.appendChild(c instanceof Node ? c : document.createTextNode(String(c))); return el; };

function css() {
  if (document.getElementById("moss-lite-css")) return;
  document.head.appendChild(h("style", { id: "moss-lite-css", textContent: `
.moss{box-sizing:border-box;width:100%;color:#e6e8ee;font:13px/1.4 system-ui,Segoe UI,sans-serif;background:#16181d;border-radius:8px}
.moss .in{display:flex;flex-direction:column;gap:8px;padding:8px}
.moss *{box-sizing:border-box}
.moss .bar{display:flex;gap:6px;align-items:center;flex-wrap:wrap}
.moss .ttl{font-weight:600;font-size:13px;color:#cfd3dc;margin-right:auto}
.moss .btn{padding:5px 11px;border-radius:7px;border:1px solid #2c313c;background:#22262e;color:#e6e8ee;cursor:pointer;font:inherit}
.moss .btn:hover{border-color:#4a5263}.moss .btn.pri{background:#3b2f63;border-color:#5b4a9a}.moss .btn.ok{background:#1f4a37;border-color:#2f7a57}
.moss .btn:disabled{opacity:.5;cursor:default}
.moss select,.moss input,.moss textarea{background:#0f1115;color:#e6e8ee;border:1px solid #2c313c;border-radius:6px;padding:4px 6px;font:inherit;min-width:0}
.moss textarea{width:100%;resize:vertical;font:12px/1.45 ui-monospace,Consolas,monospace;min-height:44px;overflow:hidden}
.moss .card{border:1px solid #262a33;border-left:3px solid var(--c,#555);border-radius:8px;padding:8px;display:flex;flex-direction:column;gap:6px;background:#1b1e24}
.moss .muted{color:#8b92a1;font-size:12px}
.moss .stage{position:relative;width:100%;background:#0e1014 repeating-linear-gradient(45deg,#12151a 0 10px,#0e1014 10px 20px);border:1px solid #2c313c;border-radius:6px;cursor:crosshair;user-select:none;touch-action:none;overflow:hidden;margin:0 auto}
.moss .box{position:absolute;border:2px solid var(--c);background:color-mix(in srgb,var(--c) 14%,transparent);cursor:move;overflow:hidden}
.moss .box.sel{box-shadow:0 0 0 2px #fff8 inset}
.moss .box .tag{position:absolute;left:0;top:0;background:var(--c);color:#0b0d10;font:600 11px system-ui;padding:0 4px;max-width:100%;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.moss .box .rz{position:absolute;right:0;bottom:0;width:12px;height:12px;background:var(--c);cursor:nwse-resize}
.moss .box img{position:absolute;right:2px;top:16px;width:34px;height:34px;object-fit:cover;border-radius:4px;border:1px solid #0008;opacity:.9;pointer-events:none}
.moss .seg{display:inline-flex;border:1px solid #2c313c;border-radius:7px;overflow:hidden}
.moss .seg button{background:#1a1d23;color:#c9cdd6;border:0;padding:4px 10px;cursor:pointer;font:inherit}
.moss .seg button.on{background:var(--c,#3b4250);color:#0b0d10;font-weight:600}
.moss .chips{display:flex;gap:4px;flex-wrap:wrap}
.moss .chip{padding:2px 8px;border-radius:10px;border:1px solid var(--c);color:#e6e8ee;cursor:pointer;font-size:12px;display:inline-flex;align-items:center;gap:4px}
.moss .chip.on{background:var(--c);color:#0b0d10}
.moss .chip img{width:18px;height:18px;object-fit:cover;border-radius:3px}
.moss .refs{display:flex;gap:8px;flex-wrap:wrap}
.moss .ref{display:flex;flex-direction:column;align-items:center;gap:2px;font-size:11px;color:#c9cdd6}
.moss .ref img,.moss .ref .ph{width:64px;height:64px;object-fit:cover;border-radius:6px;border:1px solid #2c313c;background:#0e1014;display:grid;place-items:center;color:#8b92a1}
.moss .grid2{display:grid;grid-template-columns:1fr 1fr;gap:6px}
.moss .row{display:grid;grid-template-columns:110px 1fr;gap:6px;align-items:center}
.moss .warn{color:#facc15}
` }));
}

// ------------------------------------------------------------------------------------------- widgets
const W = (node, name) => node.widgets?.find((w) => w.name === name);
const get = (node, name) => W(node, name)?.value;
function set(node, name, value) {
  const w = W(node, name);
  if (!w) return;
  w.value = value;
  w.callback?.(value);
  node.setDirtyCanvas?.(true, true);
  app.graph?.setDirtyCanvas?.(true, true);
  try { app.extensionManager?.workflow?.activeWorkflow?.changeTracker?.checkState?.(); } catch {}
}
function readBoxes(node) {
  try { const d = JSON.parse(get(node, "layout") || "{}"); return Array.isArray(d) ? d : (d.boxes || []); } catch { return []; }
}
function writeBoxes(node, boxes) {
  set(node, "layout", boxes.length ? JSON.stringify({ boxes: boxes.map((b) => ({ ...b, x: +(+b.x).toFixed(4), y: +(+b.y).toFixed(4), w: +(+b.w).toFixed(4), h: +(+b.h).toFixed(4) })) }) : "");
}
const ENH_DEFAULTS = { output: MODES[0], detail: DETAIL[0], creativity: 0.25, variation: 0 };
function enhSettings(node) {     // defaults merged in every time: an old / empty saved object never sends a missing value
  node.properties ||= {};
  const s = node.properties.moss_enhance = { ...ENH_DEFAULTS, ...(node.properties.moss_enhance || {}) };
  if (!MODES.includes(s.output)) s.output = MODES[0];
  if (!DETAIL.includes(s.detail)) s.detail = DETAIL[0];
  s.creativity = Math.min(1, Math.max(0, +s.creativity || 0)); s.variation = Math.max(0, s.variation | 0);
  return s;
}
const strictLabel = (s) => s >= 0.99 ? "exactly mine - nothing else in this box" : s >= 0.66 ? "keep my words (fix grammar only)" : s >= 0.33 ? "a little detail" : s > 0 ? "free" : "free (default)";

// ------------------------------------------------------------------------------------------- auto-growing text boxes
// A text box keeps the height you gave it (also across panel rebuilds) and grows with its text.
function autoText(st, key, props) {
  const ta = h("textarea", props);
  const fit = () => {
    if (st.taH[key]) { ta.style.height = st.taH[key]; return; }
    ta.style.height = "auto";
    ta.style.height = Math.min(520, ta.scrollHeight + 4) + "px";
  };
  ta.addEventListener("input", () => { if (st.taH[key] && ta.scrollHeight > ta.clientHeight + 2) delete st.taH[key]; fit(); });
  ta.addEventListener("pointerup", () => { if (ta.style.height && ta.offsetHeight !== ta.__h) st.taH[key] = ta.offsetHeight + "px"; });
  ta.addEventListener("pointerdown", () => { ta.__h = ta.offsetHeight; });
  if (st.taH[key]) ta.style.height = st.taH[key];     // your size, at once (no flash back to the default)
  else ta.rows = Math.min(16, Math.max(props.rows || 3, String(props.value || "").split("\n").length + Math.ceil(String(props.value || "").length / 90)));
  requestAnimationFrame(fit);
  return ta;
}

// ------------------------------------------------------------------------------------------- layout editor
function layoutCard(node, st, rebuild) {
  const boxes = readBoxes(node);
  const W_ = get(node, "width") || 1024, H_ = get(node, "height") || 1024;
  const stage = h("div.stage", { style: { aspectRatio: `${W_} / ${H_}`, maxHeight: "460px", maxWidth: `${Math.round(460 * W_ / H_)}px` }, title: "Drag on an empty place to draw a box. Drag a box to move it, its corner to resize." });
  if (boxes.length === 0) stage.appendChild(h("div.muted", { style: { position: "absolute", inset: "0", display: "grid", placeItems: "center", pointerEvents: "none", textAlign: "center", padding: "10px" } }, "Drag here to draw a box - then give it a type and its own prompt below.\nNo boxes = a normal prompt."));
  const tags = [];
  const tagText = (b, i) => `${i + 1} ${b.type}${(b.strict || 0) >= 0.99 ? " 🔒" : ""}${b.text ? ` "${b.text}"` : b.desc ? ` · ${b.desc}` : ""}`;
  const frac = (e) => { const r = stage.getBoundingClientRect(); return [Math.min(1, Math.max(0, (e.clientX - r.left) / r.width)), Math.min(1, Math.max(0, (e.clientY - r.top) / r.height))]; };
  boxes.forEach((b, i) => {
    const c = TYPES[b.type] || TYPES.object;
    const el = h("div.box" + (st.sel === i ? ".sel" : ""), { style: { "--c": c, left: `${b.x * 100}%`, top: `${b.y * 100}%`, width: `${b.w * 100}%`, height: `${b.h * 100}%` } },
      (tags[i] = h("div.tag", {}, tagText(b, i))), h("div.rz"));
    el.addEventListener("pointerdown", (e) => {
      if (e.button !== 0) return;
      e.preventDefault(); e.stopPropagation();
      st.sel = i;
      const resize = e.target.classList.contains("rz");
      const [x0, y0] = frac(e), b0 = { ...b };
      const move = (ev) => {
        const [x, y] = frac(ev), dx = x - x0, dy = y - y0;
        if (resize) { b.w = Math.max(0.02, Math.min(1 - b0.x, b0.w + dx)); b.h = Math.max(0.02, Math.min(1 - b0.y, b0.h + dy)); }
        else { b.x = Math.min(1 - b0.w, Math.max(0, b0.x + dx)); b.y = Math.min(1 - b0.h, Math.max(0, b0.y + dy)); }
        Object.assign(el.style, { left: `${b.x * 100}%`, top: `${b.y * 100}%`, width: `${b.w * 100}%`, height: `${b.h * 100}%` });
      };
      const up = () => { window.removeEventListener("pointermove", move, true); window.removeEventListener("pointerup", up, true); writeBoxes(node, boxes); rebuild(); };
      window.addEventListener("pointermove", move, true); window.addEventListener("pointerup", up, true);
    });
    stage.appendChild(el);
  });
  stage.addEventListener("pointerdown", (e) => {
    if (e.button !== 0 || e.target !== stage && !e.target.classList.contains("muted")) return;
    e.preventDefault(); e.stopPropagation();
    const [x0, y0] = frac(e);
    const ghost = h("div.box", { style: { "--c": "#ffffff", left: `${x0 * 100}%`, top: `${y0 * 100}%`, width: "0", height: "0" } });
    stage.appendChild(ghost);
    let r = null;
    const move = (ev) => { const [x, y] = frac(ev); r = { x: Math.min(x, x0), y: Math.min(y, y0), w: Math.abs(x - x0), h: Math.abs(y - y0) }; Object.assign(ghost.style, { left: `${r.x * 100}%`, top: `${r.y * 100}%`, width: `${r.w * 100}%`, height: `${r.h * 100}%` }); };
    const up = () => {
      window.removeEventListener("pointermove", move, true); window.removeEventListener("pointerup", up, true);
      ghost.remove();
      if (r && r.w > 0.02 && r.h > 0.02) { boxes.push({ ...r, type: "object", text: "", desc: "", ref: 0, strict: 0 }); st.sel = boxes.length - 1; writeBoxes(node, boxes); }
      rebuild();
    };
    window.addEventListener("pointermove", move, true); window.addEventListener("pointerup", up, true);
  });

  const b = boxes[st.sel];
  let editor = boxes.length ? h("div.muted", {}, "Click a box to edit it.") : null;
  if (b) {
    const relabel = () => { if (tags[st.sel]) tags[st.sel].textContent = tagText(b, st.sel); };
    const strictTxt = h("span.muted", {}, strictLabel(b.strict || 0));
    editor = h("div.card", { style: { "--c": TYPES[b.type] } },
      h("div.bar", {}, h("b", {}, `Box ${st.sel + 1}`),
        h("div.seg", {}, Object.keys(TYPES).map((t) => h("button" + (b.type === t ? ".on" : ""), { style: { "--c": TYPES[t] }, on: { click: () => { b.type = t; writeBoxes(node, boxes); rebuild(); } } }, t))),
        h("span", { style: { marginLeft: "auto" } }),
        h("button.btn", { title: "Draw earlier (further back)", on: { click: () => { if (st.sel > 0) { boxes.splice(st.sel - 1, 0, boxes.splice(st.sel, 1)[0]); st.sel--; writeBoxes(node, boxes); rebuild(); } } } }, "◀ back"),
        h("button.btn", { title: "Draw later (further front)", on: { click: () => { if (st.sel < boxes.length - 1) { boxes.splice(st.sel + 1, 0, boxes.splice(st.sel, 1)[0]); st.sel++; writeBoxes(node, boxes); rebuild(); } } } }, "front ▶"),
        h("button.btn", { on: { click: () => { boxes.splice(st.sel, 1); st.sel = null; writeBoxes(node, boxes); rebuild(); } } }, "Delete")),
      b.type === "text" ? h("input", { type: "text", placeholder: "Exact words to write (\\n = new line)", value: b.text || "", on: { input: (e) => { b.text = e.target.value; writeBoxes(node, boxes); relabel(); } } }) : null,
      autoText(st, `box${st.sel}`, { rows: 3, placeholder: b.type === "text" ? "How the text looks: typeface, colour, size, where it is printed..." : "What is in this box (its own prompt)...", value: b.desc || "", on: { input: (e) => { b.desc = e.target.value; writeBoxes(node, boxes); relabel(); } } }),
      h("div.row", {}, h("span.muted", { title: "How much the enhancer may change this box, and at 0.5+ the render keeps everything else out of it." }, "strict"),
        h("div.bar", {}, h("input", { type: "range", min: 0, max: 1, step: 0.05, value: b.strict || 0, style: { flex: "1" },
          on: { input: (e) => { b.strict = +e.target.value; strictTxt.textContent = `${(+b.strict).toFixed(2)} · ${strictLabel(b.strict)}`; writeBoxes(node, boxes); relabel(); } } }), strictTxt)));
    strictTxt.textContent = `${(+(b.strict || 0)).toFixed(2)} · ${strictLabel(b.strict || 0)}`;
  }
  return h("div.card", { style: { "--c": "#4fb3ff" } },
    h("div.bar", {}, h("span.ttl", {}, `📐 Layout boxes (${boxes.length})`), h("span.muted", {}, `${W_}×${H_}`),
      boxes.length ? h("button.btn", { on: { click: () => { st.sel = null; writeBoxes(node, []); rebuild(); } } }, "Clear all") : null),
    stage,
    boxes.length ? h("div.chips", {}, boxes.map((x, i) => h("span.chip" + (st.sel === i ? ".on" : ""), { style: { "--c": TYPES[x.type] }, on: { click: () => { st.sel = i; rebuild(); } } }, `${i + 1} ${x.type}${(x.strict || 0) >= 0.99 ? " 🔒" : ""}`))) : null,
    editor);
}

// ------------------------------------------------------------------------------------------- enhance (separate small job)
const PENDING = new Map();   // preview node id -> {resolve, reject, prompt_id}
api.addEventListener("executed", (e) => {
  const key = String(e.detail?.node ?? e.detail?.display_node);
  const p = PENDING.get(key);
  if (p) { PENDING.delete(key); p.resolve((e.detail.output?.text || []).join("")); }
});
api.addEventListener("execution_error", (e) => {
  const d = e.detail || {};
  for (const [k, p] of PENDING) {
    if (p.prompt_id === d.prompt_id || (p.prompt_id == null && String(d.node_id || "").startsWith("moss_enh_"))) {
      PENDING.delete(k); p.reject(new Error(d.exception_message || "the job failed"));
    }
  }
});

async function runEnhance(node, st, rebuild) {
  const s = node.properties.moss_enhance || enhSettings(node);
  const text = get(node, "prompt") || "";
  const boxes = readBoxes(node);
  if (!text.trim() && !boxes.length) { st.enh = { error: "Write your idea in the prompt (or draw boxes) first." }; rebuild(); return; }
  st.enh = { busy: true, t0: Date.now() }; rebuild();
  try {
    const { output } = await app.graphToPrompt();
    const mine = output[String(node.id)] || Object.values(output).find((n) => n.class_type === GEN);
    if (!mine?.inputs?.clip) throw new Error("Connect the CLIPLoader to MOSS Generate first.");
    const id = `moss_enh_${Date.now()}`;
    const prompt = {};
    const need = (key) => { const n = output[key]; if (!n || prompt[key]) return; prompt[key] = n; for (const v of Object.values(n.inputs || {})) if (Array.isArray(v) && v.length === 2 && output[v[0]]) need(String(v[0])); };
    need(String(mine.inputs.clip[0]));
    const inputs = { clip: mine.inputs.clip, text, enhance: true, output: s.output, detail: s.detail, creativity: s.creativity, variation: s.variation,
      width: get(node, "width"), height: get(node, "height"), layout: boxes.length ? get(node, "layout") : "" };
    prompt[id] = { class_type: ENH, inputs };
    const outs = { p: 0, r: 3, l: 4 };
    for (const [suffix, slot] of Object.entries(outs)) prompt[`${id}_${suffix}`] = { class_type: "PreviewAny", inputs: { source: [id, slot] } };
    const keys = Object.keys(outs).map((k) => `${id}_${k}`);
    const waits = keys.map((key) => new Promise((resolve, reject) => PENDING.set(key, { resolve, reject })));
    const res = await api.fetchApi("/prompt", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ prompt, client_id: api.clientId, partial_execution_targets: keys }) });
    const body = await res.json();
    if (!res.ok || body.error) { keys.forEach((k) => PENDING.delete(k)); throw new Error(body.error?.message || JSON.stringify(body.node_errors || body).slice(0, 300)); }
    for (const k of keys) { const p = PENDING.get(k); if (p) p.prompt_id = body.prompt_id; }   // a fast job may already be done
    const [after, report, layoutOut] = await Promise.all(waits);
    const secs = (Date.now() - st.enh.t0) / 1000;
    if (boxes.length) {
      let newBoxes = boxes;
      try { newBoxes = JSON.parse(layoutOut || "{}").boxes || boxes; } catch {}
      st.enh = { kind: "boxes", beforePrompt: text, afterPrompt: after, rows: boxes.map((b, i) => ({ n: i + 1, type: b.type, before: b.desc || "", after: newBoxes[i]?.desc ?? b.desc ?? "", locked: (b.strict || 0) >= 0.99 })), report, secs };
    } else st.enh = { kind: "text", before: text, after, report, secs };
  } catch (err) { st.enh = { error: String(err?.message || err) }; }
  rebuild();
}

function applyText(node, after) {
  let layout = null;
  try { const d = JSON.parse(after); if (d && Array.isArray(d.items) && d.summary) layout = d; } catch {}
  if (layout) {          // a Layout answer: global caption -> prompt, items -> editable boxes on the canvas
    const W_ = get(node, "width") || 1024, H_ = get(node, "height") || 1024;
    const boxes = layout.items.map((it) => { const [y1, x1, y2, x2] = it.bbox; return { x: (x1 + W_ / 2) / W_, y: (y1 + H_ / 2) / H_, w: (x2 - x1) / W_, h: (y2 - y1) / H_, type: ["object", "character", "text"].includes(it.label) ? it.label : "object", text: it.text || "", desc: it.caption || "", ref: 0, strict: 0 }; });
    set(node, "prompt", layout.summary.caption || "");
    writeBoxes(node, boxes);
  } else set(node, "prompt", after);
}

function reviewBody(node, st, rebuild) {
  const e = st.enh;
  if (e.kind === "boxes") {
    const main = autoText(st, "enh_main", { value: e.afterPrompt });
    const rows = e.rows.map((r) => ({ r, ta: r.locked ? null : autoText(st, `enh_box${r.n}`, { value: r.after }) }));
    return h("div", { style: { display: "flex", flexDirection: "column", gap: "6px" } },
      h("div.muted", {}, `${e.report || ""} · ${e.secs?.toFixed(1)}s`),
      h("div.muted", {}, "Global description - before:"), h("div", { style: { whiteSpace: "pre-wrap", opacity: 0.75, fontSize: "12px" } }, e.beforePrompt || "(empty)"),
      h("div.muted", {}, "after (edit it if you like):"), main,
      rows.map(({ r, ta }) => h("div.card", { style: { "--c": TYPES[r.type] } },
        h("div.bar", {}, h("b", {}, `Box ${r.n} · ${r.type}`), r.locked ? h("span.muted", {}, "🔒 strict 1 - kept exactly") : null),
        h("div", { style: { whiteSpace: "pre-wrap", opacity: 0.75, fontSize: "12px" } }, r.before || "(empty)"),
        ta)),
      h("div.bar", {},
        h("button.btn.ok", { on: { click: () => {
          const boxes = readBoxes(node);
          for (const { r, ta } of rows) if (ta && boxes[r.n - 1]) boxes[r.n - 1].desc = ta.value;
          set(node, "prompt", main.value);
          writeBoxes(node, boxes);
          st.enh = null; rebuild();
        } } }, "✓ Apply (prompt + each box)"),
        h("button.btn", { on: { click: () => { st.enh = null; rebuild(); } } }, "Discard")));
  }
  const ta = autoText(st, "enh_after", { value: e.after });
  return h("div", { style: { display: "flex", flexDirection: "column", gap: "6px" } },
    h("div.muted", {}, `${e.report || ""} · ${e.secs?.toFixed(1)}s`),
    h("div.grid2", {}, h("div", {}, h("div.muted", {}, "Before (yours)"), autoText(st, "enh_before", { value: e.before, readOnly: true })), h("div", {}, h("div.muted", {}, "After (edit it if you like)"), ta)),
    h("div.bar", {}, h("button.btn.ok", { on: { click: () => { applyText(node, ta.value); st.enh = null; rebuild(); } } }, "✓ Apply (replaces the prompt" + (e.after.trim().startsWith("{") ? " + boxes)" : ")")),
      h("button.btn", { on: { click: () => { st.enh = null; rebuild(); } } }, "Discard")));
}

function enhanceCard(node, st, rebuild) {
  const s = enhSettings(node);
  const boxes = readBoxes(node).length;
  const sel = (key, opts) => h("select", { disabled: !!(boxes && key === "output"), on: { change: (e) => { s[key] = e.target.value; } } }, opts.map((o) => h("option", { value: o, selected: s[key] === o }, o)));
  const e = st.enh;
  let body = null;
  if (e?.busy) body = h("div.muted", {}, boxes ? `Qwen3.5-9B is rewriting each of the ${boxes} boxes on its own (a separate small job - nothing is rendered)...` : "Qwen3.5-9B is rewriting your prompt (a separate small job - nothing is rendered)...");
  else if (e?.error) body = h("div", { style: { color: "#f87171" } }, e.error);
  else if (e?.kind) body = reviewBody(node, st, rebuild);
  return h("div.card", { style: { "--c": "#a78bfa" } },
    h("div.bar", {}, h("span.ttl", {}, "✨ Prompt enhancer (MOSS's own Qwen3.5-9B)"),
      h("button.btn.pri", { disabled: !!e?.busy, on: { click: () => runEnhance(node, st, rebuild) } }, e?.busy ? "Rewriting..." : boxes ? "✨ Enhance each box" : "✨ Enhance")),
    h("div.bar", {}, h("span.muted", {}, "output"), sel("output", MODES), h("span.muted", {}, "detail"), sel("detail", DETAIL)),
    boxes ? h("div.muted", {}, `With boxes: each box is rewritten on its own (its strict slider sets how freely), the prompt becomes the global description; places and words never change.`) : null,
    h("div.bar", {}, h("span.muted", {}, "creativity"),
      h("input", { type: "range", min: 0, max: 1, step: 0.05, value: s.creativity, style: { flex: "1" }, on: { input: (ev) => { s.creativity = +ev.target.value; ev.target.nextSibling.textContent = (+ev.target.value).toFixed(2); } } }),
      h("span", {}, (+s.creativity).toFixed(2)),
      h("span.muted", {}, "variation"), h("input", { type: "number", min: 0, value: s.variation, style: { width: "70px" }, on: { change: (ev) => { s.variation = Math.max(0, ev.target.value | 0); } } })),
    body);
}

function reportCard(node, st) {
  if (!st.report) return null;
  return h("div.card", { style: { "--c": "#3ccf91" } },
    h("div.muted", {}, "Last render: " + st.report),
    h("details", {}, h("summary", { class: "muted", style: { cursor: "pointer" } }, "Final prompt (exactly what MOSS read)"), autoText(st, "final", { value: st.final || "", readOnly: true })));
}

// ------------------------------------------------------------------------------------------- canvas navigation
// The wheel over the panel zooms the canvas (never changes a value); Alt+wheel scrolls inside a text box.
function navigation(root) {
  root.addEventListener("wheel", (e) => {
    if (e.altKey) return;
    e.preventDefault(); e.stopPropagation();
    app.canvas?.canvas?.dispatchEvent(new WheelEvent("wheel", { bubbles: true, cancelable: true, clientX: e.clientX, clientY: e.clientY, deltaX: e.deltaX, deltaY: e.deltaY, deltaMode: e.deltaMode, ctrlKey: e.ctrlKey, shiftKey: e.shiftKey, metaKey: e.metaKey }));
  }, { passive: false, capture: true });
  for (const ev of ["keydown", "keyup", "keypress"]) root.addEventListener(ev, (e) => e.stopPropagation());
}

// ------------------------------------------------------------------------------------------- node setup
function attach(node) {
  if (node.__moss) return;
  css();
  const inner = h("div.in");
  const root = h("div.moss", {}, inner);
  navigation(root);
  node.properties ||= {};
  // text box sizes you set are kept in the workflow (node properties), so they survive rebuilds and reloads
  const st = { sel: null, enh: null, report: "", final: "", taH: (node.properties.moss_textsize ||= {}), need: 600 };
  const lay = W(node, "layout");
  if (lay) { lay.hidden = true; if (lay.options) lay.options.hidden = true; }
  // Auto-fit only GROWS the node when its content needs more room: a node you made bigger is never shrunk back
  // (adding a box, a render, Enhance...). Shrinking happens only with "Fit the panel now" (force).
  const fit = (force = false) => {
    const need = Math.ceil(inner.scrollHeight) + 4;
    st.need = need;
    if (!force && node.properties?.moss_autofit === false) return;
    const target = node.computeSize?.()[1];
    if (!target) return;
    if (force ? Math.abs(node.size[1] - target) > 2 : target > node.size[1] + 2) {
      node.setSize([node.size[0], target]);
      node.setDirtyCanvas?.(true, true);
    }
  };
  const rebuild = () => {
    try { put(inner, enhanceCard(node, st, rebuild), layoutCard(node, st, rebuild), reportCard(node, st)); }
    catch (err) { put(inner, h("div", { style: { color: "#f87171" } }, "Panel error: " + (err?.message || err))); console.error("[MOSS Studio]", err); }
    setTimeout(() => fit(), 30);         // a timer, not a frame: also runs while the tab is in the background
  };
  const widget = node.addDOMWidget("moss_panel", "moss_panel", root, { serialize: false, hideOnZoom: false, hideInPanel: true, getValue: () => "", setValue: () => {}, getMinHeight: () => st.need });
  widget.serialize = false;
  node.__moss = { root, st, rebuild };
  try { new ResizeObserver(() => fit()).observe(inner); } catch {}
  for (const name of ["width", "height"]) {
    const w = W(node, name);
    if (!w) continue;
    const cb = w.callback;
    w.callback = function () { const r = cb?.apply(this, arguments); queueMicrotask(rebuild); return r; };
  }
  const conn = node.onConnectionsChange;
  node.onConnectionsChange = function () { const r = conn?.apply(this, arguments); queueMicrotask(rebuild); return r; };
  const configure = node.onConfigure;
  node.onConfigure = function () { this.__mossLoaded = true; const r = configure?.apply(this, arguments); st.taH = (this.properties.moss_textsize ||= {}); queueMicrotask(rebuild); return r; };
  setTimeout(() => {       // a brand-new node starts on a random seed (a loaded one keeps its own)
    const seed = W(node, "seed");
    if (!node.__mossLoaded && seed && !seed.value) seed.value = Math.floor(Math.random() * 2 ** 48);
  }, 0);
  const executed = node.onExecuted;
  node.onExecuted = function (out) { const r = executed?.apply(this, arguments); st.report = (out?.moss_report || []).join(""); st.final = (out?.moss_prompt || []).join(""); rebuild(); return r; };
  const menu = node.getExtraMenuOptions;
  node.getExtraMenuOptions = function (canvas, options) {
    const r = menu?.apply(this, arguments);
    const on = this.properties?.moss_autofit !== false;
    options?.push?.(null, { content: `Auto-grow height: ${on ? "ON (click to turn off)" : "OFF (click to turn on)"}`, callback: () => { this.properties.moss_autofit = !on; st.need = 0; fit(); } },
      { content: "Fit the panel now (shrink to content)", callback: () => fit(true) });
    return r;
  };
  node.setSize([Math.max(node.size[0], 560), node.size[1]]);
  setTimeout(rebuild, 0);
}

app.registerExtension({
  name: "SatoDive.MOSSStudioLite",
  nodeCreated(node) { if ((node.comfyClass || node.type) === GEN) attach(node); },
});
