// Package cutaway for the board viewer: lead frame, die and bond wires of an IC, with the die surface drawn as the
// IC's internal circuit. Circuit content comes from internals.json, which follows each datasheet's own figures
// (block diagrams, and transistors where the datasheet draws them). Die size and floorplan are not published by the
// manufacturers: the die is sized to fit the package's die paddle and its blocks sit next to the pins they serve.
import * as THREE from 'three';
import { COL, drawFet, drawAmp, drawTwo, cellLayout, drawBlock } from './cells.js';

const MAT = {
  frame: new THREE.MeshStandardMaterial({ color: 0xc89a6a, metalness: 0.8, roughness: 0.35 }),   // copper lead frame
  gold: new THREE.MeshStandardMaterial({ color: 0xf2c75c, metalness: 1.0, roughness: 0.22 }),    // bond wire
  dieSide: new THREE.MeshStandardMaterial({ color: 0x59606e, metalness: 0.4, roughness: 0.45 }),
  ghost: new THREE.LineBasicMaterial({ color: 0x9fb3c8, transparent: true, opacity: 0.6 }),
  shell: new THREE.MeshBasicMaterial({ color: 0x202020, transparent: true, opacity: 0.1, depthWrite: false }),
};
const UNIT = new THREE.BoxGeometry(1, 1, 1);

// package mm (x right, y away from the viewer, z up) -> three.js part space (x, up, -y)
const V3 = (x, y, z) => new THREE.Vector3(x, z, -y);

function slab(g, x, y, w, d, h, m, z0 = 0) {
  const o = new THREE.Mesh(UNIT, m); o.scale.set(w, h, d); o.position.copy(V3(x, y, z0 + h / 2)); g.add(o); return o;
}
// flat strip from a to b ([x, y, z] each), width w across, thickness t
function strip(g, a, b, w, t, m) {
  const A = V3(...a), B = V3(...b), X = B.clone().sub(A), len = X.length();
  X.normalize();
  const Z = new THREE.Vector3().crossVectors(X, new THREE.Vector3(0, 1, 0));
  if (Z.lengthSq() < 1e-9) Z.set(1, 0, 0);
  Z.normalize();
  const Y = new THREE.Vector3().crossVectors(Z, X).normalize();
  const o = new THREE.Mesh(UNIT, m);
  o.quaternion.setFromRotationMatrix(new THREE.Matrix4().makeBasis(X, Y, Z));
  o.scale.set(len, t, w); o.position.copy(A).add(B).multiplyScalar(0.5); g.add(o);
}

// ------------------------------------------------------------------ pins -> bond pads
const padKey = pad => (/^P\d+$/.test(pad) ? String(+pad.slice(1)) : pad);
// datasheet pin name: from the spec, else the port name in the schematic's pin name ("(OC0B)PG5" -> PG5)
function pinName(spec, r) {
  const k = padKey(r.pad);
  if (spec.pins && spec.pins[k]) return spec.pins[k];
  const m = /P[A-L][0-7]/.exec(r.pin || '');
  if (m) return m[0];
  return (r.pin || k).replace(/\d+$/, '');
}

// Bond pad layout on the die (die units: 1000 across x, v down = package -y) plus the matching lead tip in mm
export function padLayout(p, spec) {
  const pk = spec.pkg, [dw, dd] = pk.die, Vd = 1000 * dd / dw;
  const pins = (p.pins || []).filter(r => r.at && !(pk.epad || []).includes(r.pad))
    .map(r => ({ r, name: pinName(spec, r), x: r.at[0], y: r.at[1] }))
    .filter(q => !/^NC/.test(q.name));
  const quad = pk.kind !== 'dual';
  const xmax = Math.max(...pins.map(q => Math.abs(q.x))), ymax = Math.max(...pins.map(q => Math.abs(q.y)));
  const rowsInX = new Set(pins.map(q => Math.round(q.x * 10))).size === 2;
  for (const q of pins) {
    if (quad) q.side = Math.abs(q.x) / xmax >= Math.abs(q.y) / ymax ? (q.x < 0 ? 'L' : 'R') : (q.y > 0 ? 'T' : 'B');
    else q.side = rowsInX ? (q.x < 0 ? 'L' : 'R') : (q.y > 0 ? 'T' : 'B');
  }
  const alongMax = s => Math.max(...pins.filter(q => q.side === s || q.side === { L: 'R', R: 'L', T: 'B', B: 'T' }[s])
    .map(q => Math.abs('LR'.includes(s) ? q.y : q.x)), 1e-6);
  const m = pk.margin ?? 120, e = pk.inset ?? 55, S = pk.padS ?? 46;
  const bw = p.body.w, bd = p.body.d;
  for (const q of pins) {
    const lr = 'LR'.includes(q.side), t = (lr ? q.y : q.x) / alongMax(q.side);
    q.t = t;
    if (q.side === 'L') { q.u = e; q.v = Vd / 2 - t * (Vd / 2 - m); q.n = [1, 0]; }
    if (q.side === 'R') { q.u = 1000 - e; q.v = Vd / 2 - t * (Vd / 2 - m); q.n = [-1, 0]; }
    if (q.side === 'T') { q.v = e; q.u = 500 + t * (500 - m); q.n = [0, 1]; }
    if (q.side === 'B') { q.v = Vd - e; q.u = 500 + t * (500 - m); q.n = [0, -1]; }
    q.inner = [q.u + q.n[0] * S / 2, q.v + q.n[1] * S / 2];
    q.mm = [(q.u / 1000 - 0.5) * dw, (0.5 - q.v / Vd) * dd];
    // where the wire lands: inner end of the QFN terminal, or the tip of the leaded part's inner lead
    if (pk.kind === 'qfn') {
      const L = pk.term[1] - 0.08;
      q.tip = q.side === 'L' ? [-bw / 2 + L, q.y] : q.side === 'R' ? [bw / 2 - L, q.y]
            : q.side === 'T' ? [q.x, bd / 2 - L] : [q.x, -bd / 2 + L];
    } else {
      const [rx, ry] = pk.tip, sp = pk.tipSpan ?? [rx - 0.3, ry - 0.3];
      q.tip = q.side === 'L' ? [-rx, t * sp[1]] : q.side === 'R' ? [rx, t * sp[1]]
            : q.side === 'T' ? [t * sp[0], ry] : [t * sp[0], -ry];
    }
  }
  return { pins, Vd, S };
}

// ------------------------------------------------------------------ die drawing
function drawDie(spec, lay) {
  const pk = spec.pkg, px = pk.tex ?? 2048, k = px / 1000, Vd = lay.Vd, ui = pk.ui ?? 1;
  const c = document.createElement('canvas'); c.width = px; c.height = Math.round(Vd * k);
  const x = c.getContext('2d'); x.scale(k, k); x.lineCap = 'round'; x.lineJoin = 'round';
  x.fillStyle = COL.bg; x.fillRect(0, 0, 1000, Vd);
  x.strokeStyle = COL.grid; x.lineWidth = 1;
  for (let g = 0; g <= 1000; g += 25) { x.beginPath(); x.moveTo(g, 0); x.lineTo(g, Vd); x.stroke(); }
  for (let g = 0; g <= Vd; g += 25) { x.beginPath(); x.moveTo(0, g); x.lineTo(1000, g); x.stroke(); }
  x.strokeStyle = COL.seal; x.lineWidth = 5; x.strokeRect(6, 6, 988, Vd - 12);

  const font = (s, w = '') => `${w} ${s * ui}px system-ui, sans-serif`;
  const pads = new Map(), byPad = new Map();
  for (const q of lay.pins) { if (!pads.has(q.name)) pads.set(q.name, q); byPad.set(padKey(q.r.pad), q); }
  const ids = {};
  // resolve a point: [u, v], "@NAME" pad, "#n" pad no., "id.t" terminal; either coordinate of [u, v] may itself be a
  // reference, which takes that coordinate from it ([480, "CP.cp1"] = x 480 at the height of CP.cp1)
  const P = ref => {
    if (Array.isArray(ref)) return ref.map((c2, i) => (typeof c2 === 'string' ? P(c2)[i] : c2));
    if (ref[0] === '@') { const q = pads.get(ref.slice(1)); if (!q) throw new Error('no pad ' + ref); return q.inner; }
    if (ref[0] === '#') return byPad.get(ref.slice(1)).inner;
    const [id, t] = ref.split('.'); const it = ids[id];
    if (!it || !it.T[t]) throw new Error('no terminal ' + ref);
    return it.T[t];
  };
  const line = (pts, col = COL.wire, w = 2.2) => {
    x.strokeStyle = col; x.lineWidth = w * ui; x.beginPath();
    pts.forEach((q, i) => (i ? x.lineTo(q[0], q[1]) : x.moveTo(q[0], q[1]))); x.stroke();
  };
  const text = (s, u, v, size = 14, align = 'center', col = COL.txt, rot = 0, weight = '') => {
    x.save(); x.translate(u, v); if (rot) x.rotate(rot * Math.PI / 180);
    x.fillStyle = col; x.font = font(size, weight); x.textAlign = align; x.textBaseline = 'middle';
    String(s).split('\n').forEach((l, i, a) => x.fillText(l, 0, (i - (a.length - 1) / 2) * size * ui * 1.15));
    x.restore();
  };
  const kcol = k2 => ({ pwr: COL.pwr, gnd: COL.gnd, sig: COL.sig, vcc: COL.vcc })[k2] || COL.wire;
  const kw = k2 => (k2 === 'pwr' || k2 === 'gnd' ? 4 : 2.2);

  // terminals of the drawn elements, by element type, before anything references them
  for (const it of spec.draw || []) {
    const T = {}, s = it.s ?? 40;
    if (it.t === 'box') {
      const { x: u, y: v, w, h } = it;
      Object.assign(T, { l: [u, v + h / 2], r: [u + w, v + h / 2], t: [u + w / 2, v], b: [u + w / 2, v + h] });
      for (const f of [0.2, 0.25, 0.3, 0.33, 0.4, 0.5, 0.6, 0.67, 0.7, 0.75, 0.8]) {
        const n = String(f).slice(2);
        T['l' + n] = [u, v + h * f]; T['r' + n] = [u + w, v + h * f]; T['t' + n] = [u + w * f, v]; T['b' + n] = [u + w * f, v + h];
      }
      if (it.ckt) for (const [n, pt] of Object.entries(cellLayout(it.ckt, it, it).ports)) T[n] = pt.edge;
    } else if (it.t === 'n' || it.t === 'p') {
      const gs = it.gr ? 1 : -1, fy = it.fy ? -1 : 1;
      Object.assign(T, { d: [it.x, it.y - s * fy], s: [it.x, it.y + s * fy], g: [it.x + gs * s, it.y] });
    } else if (it.t === 'amp' || it.t === 'buf' || it.t === 'inv' || it.t === 'st') {
      const d = { r: [1, 0], l: [-1, 0], u: [0, -1], d: [0, 1] }[it.dir || 'r'], nx = -d[1], ny = d[0];
      T.o = [it.x + d[0] * s, it.y + d[1] * s]; T.i = [it.x - d[0] * s, it.y - d[1] * s];
      T.a = [it.x - d[0] * s - nx * s * 0.45, it.y - d[1] * s - ny * s * 0.45];
      T.b = [it.x - d[0] * s + nx * s * 0.45, it.y - d[1] * s + ny * s * 0.45];
      T.e = [it.x + nx * s * 0.5, it.y + ny * s * 0.5];                     // enable / supply side
    } else if (it.t === 'osc') {
      const r = it.r ?? 30; Object.assign(T, { l: [it.x - r, it.y], r: [it.x + r, it.y], t: [it.x, it.y - r], b: [it.x, it.y + r] });
    }
    if (it.id) ids[it.id] = { it, T };
  }

  const blocks = [];                                   // transistor-level blocks, also rendered as sharper overlays
  if (spec.ring === 'avr') drawAvrRing(x, spec, lay, { line, text, ui });
  if (spec.core) drawCore(x, spec.core, { line, text, ui }, blocks);

  // bond pads
  for (const q of lay.pins) {
    const S = lay.S;
    x.fillStyle = COL.pad; x.fillRect(q.u - S / 2, q.v - S / 2, S, S);
    x.strokeStyle = '#8f98a6'; x.lineWidth = 2; x.strokeRect(q.u - S / 2 + 4, q.v - S / 2 + 4, S - 8, S - 8);
    const lr = 'LR'.includes(q.side), off = S / 2 + 6;   // name beside the pad's wire, not on it
    const up = (pk.labelBelow || []).includes(padKey(q.r.pad)) ? -15 : 15;   // corner pads: below, clear of the next side
    const lu = q.u + q.n[0] * off + (lr ? 0 : 17), lv = q.v + q.n[1] * off - (lr ? up : 0), rot = lr ? 0 : -90;
    const align = q.side === 'L' || q.side === 'B' ? 'left' : 'right';
    if (!spec.ring) text(q.name, lu, lv, pk.padFont ?? 13, align, COL.txt, rot, '600');
    text(padKey(q.r.pad), q.u, q.v, Math.min(S * 0.42, 16), 'center', COL.padTxt, 0, '700');
  }

  // circuit
  for (const it of spec.draw || []) {
    const s = it.s ?? 40, col = kcol(it.k);
    switch (it.t) {
      case 'w': case 'arrow': {
        const pts = [];
        for (const ref of it.p) {
          const q = P(ref), prev = pts[pts.length - 1];       // null: keep the previous point's coordinate
          pts.push(Array.isArray(ref) ? [q[0] ?? prev[0], q[1] ?? prev[1]] : q);
        }
        line(pts, col, it.wd ?? kw(it.k));
        if (it.t === 'arrow') {
          const [a, b] = pts.slice(-2), ang = Math.atan2(b[1] - a[1], b[0] - a[0]), h = 12 * ui;
          x.fillStyle = col; x.beginPath(); x.moveTo(b[0], b[1]);
          x.lineTo(b[0] - h * Math.cos(ang - 0.4), b[1] - h * Math.sin(ang - 0.4));
          x.lineTo(b[0] - h * Math.cos(ang + 0.4), b[1] - h * Math.sin(ang + 0.4)); x.fill();
        }
        for (const d of it.dots || []) { x.fillStyle = col; x.beginPath(); x.arc(...P(d), 5 * ui, 0, 7); x.fill(); }
        break;
      }
      case 'dot': { x.fillStyle = col; x.beginPath(); x.arc(...P(it.p), 5 * ui, 0, 7); x.fill(); break; }
      case 'txt': text(it.l, it.p[0], it.p[1], it.s ?? 13, it.a ?? 'center', it.c ? COL[it.c] : COL.txt, it.r ?? 0, it.b ? '600' : ''); break;
      case 'box': {
        if (it.ckt) { drawBlock(x, it, it, ui); blocks.push({ r: it, o: it }); break; }
        x.fillStyle = it.fill ?? COL.box; x.fillRect(it.x, it.y, it.w, it.h);
        x.strokeStyle = it.k ? col : COL.boxLine; x.lineWidth = 2 * ui; if (it.dash) x.setLineDash([10, 7]);
        x.strokeRect(it.x, it.y, it.w, it.h); x.setLineDash([]);
        if (it.l) text(it.l, it.x + it.w / 2, it.ly ?? it.y + it.h / 2, it.fs ?? 14, 'center', COL.txt, it.lr ?? 0);
        break;
      }
      case 'n': case 'p': drawFet(x, it, s, ui); break;
      case 'amp': case 'buf': case 'inv': case 'st': drawAmp(x, it, s, ui, text); break;
      case 'osc': {
        const r = it.r ?? 30; x.strokeStyle = COL.boxLine; x.lineWidth = 2 * ui; x.fillStyle = COL.box;
        x.beginPath(); x.arc(it.x, it.y, r, 0, 7); x.fill(); x.stroke(); text(it.l ?? 'OSC', it.x, it.y, it.fs ?? 12); break;
      }
      case 'res': case 'cap': case 'dio': case 'coil': drawTwo(x, it, P(it.a), P(it.b), ui, text); break;
      case 'gnd': {
        const [u, v] = P(it.p); line([[u, v], [u, v + 10]], COL.gnd, 2.2);
        for (const [w, o] of [[22, 10], [14, 16], [6, 22]]) line([[u - w / 2, v + o], [u + w / 2, v + o]], COL.gnd, 2.2);
        break;
      }
    }
  }
  if (spec.caption) text(spec.caption, 500, Vd - (pk.capY ?? 22), pk.capFont ?? 11, 'center', COL.muted);
  return { canvas: c, blocks };
}

// AVR I/O ring: every port pin gets the pin circuit of the datasheet's "I/O Pin Equivalent Schematic" and
// "General Digital I/O" figures: clamp diodes to VCC and GND, switchable pull-up (PMOS + Rpu), tri-state output
// driver and Schmitt-trigger input. Supply pads tie to the VCC and GND rings; other pads are labelled.
function drawAvrRing(x, spec, lay, h) {
  const { line, text } = h, r = spec.ringDepth, Vd = lay.Vd, e = spec.pkg.inset ?? 55;
  const ring = (d, col) => line([[d, d], [1000 - d, d], [1000 - d, Vd - d], [d, Vd - d], [d, d]], col, 3);
  ring(r.vcc, COL.vcc); ring(r.gnd, COL.gnd);
  const sides = { L: [], R: [], T: [], B: [] };
  for (const q of lay.pins) sides[q.side].push(q);
  for (const [s, qs] of Object.entries(sides)) {
    qs.sort((a, b) => ('LR'.includes(s) ? a.v - b.v : a.u - b.u));
    const pitch = qs.length > 1 ? Math.abs(('LR'.includes(s) ? qs[1].v - qs[0].v : qs[1].u - qs[0].u)) : 100;
    for (const q of qs) {
      x.save(); x.translate(q.u, q.v);
      x.rotate({ L: -Math.PI / 2, R: Math.PI / 2, T: 0, B: Math.PI }[s]);   // local +y points into the die
      drawCell(x, q, pitch, { vcc: r.vcc - e, gnd: r.gnd - e, cell: r.cell - e }, lay.S / 2, h.ui, s);
      x.restore();
    }
  }
  text('VCC', r.vcc + 8, r.vcc - 9, 9, 'left', COL.vcc); text('GND', r.gnd + 8, r.gnd - 9, 9, 'left', COL.gnd);
}

// one pad cell, local frame: pad centre at the origin, +y into the die, rings at depth r.vcc / r.gnd
function drawCell(x, q, pitch, r, y0, ui, side) {
  const k = Math.min(pitch * 0.32, 16), off = Math.min(pitch * 0.3, 20);   // symbol size, sideways spread
  pitch = off / 0.3;
  const L = (pts, col = COL.wire, w = 1.6) => {
    x.strokeStyle = col; x.lineWidth = w * ui; x.beginPath(); pts.forEach((p, i) => (i ? x.lineTo(...p) : x.moveTo(...p))); x.stroke();
  };
  const dot = (u, v, col = COL.wire) => { x.fillStyle = col; x.beginPath(); x.arc(u, v, 2.6 * ui, 0, 7); x.fill(); };
  const diode = (u, va, vb, col) => {                    // vertical diode, anode at va, cathode at vb
    const m = (va + vb) / 2, d = vb > va ? 1 : -1, z = k * 0.4;
    L([[u, va], [u, m - d * z]], col); L([[u, m + d * z * 0.8], [u, vb]], col);
    x.fillStyle = col; x.beginPath(); x.moveTo(u - z, m - d * z); x.lineTo(u + z, m - d * z); x.lineTo(u, m + d * z * 0.8);
    x.closePath(); x.fill(); L([[u - z, m + d * z * 0.8], [u + z, m + d * z * 0.8]], col);
  };
  const label = (s, v, col = COL.txt, size = 10) => {    // reads along the cell, upright on the right-hand side
    x.save(); x.translate(0, v); x.rotate(Math.PI / 2 + (side === 'R' ? Math.PI : 0));
    x.fillStyle = col; x.font = `600 ${size * ui}px system-ui, sans-serif`; x.textAlign = 'center'; x.textBaseline = 'middle';
    x.fillText(s, 0, 0); x.restore();
  };
  const n = q.name;
  if (/^(VCC|AVCC|UVCC)$/.test(n)) {
    L([[0, y0], [0, r.vcc]], COL.vcc, 3); dot(0, r.vcc, COL.vcc);
    if (n !== 'VCC') { L([[0, r.vcc], [0, r.gnd + 30]], COL.vcc, 2); label(n === 'AVCC' ? 'AVCC → A/D' : 'UVCC → 3.3 V reg.', r.cell - 60, COL.vcc); }
    return;
  }
  if (/^(GND|UGND)$/.test(n)) { L([[0, y0], [0, r.gnd]], COL.gnd, 3); dot(0, r.gnd, COL.gnd); return; }
  const io = /^P[A-L][0-7]$/.test(n);
  if (!io) {                                             // XTAL, RESET, AREF, UCAP, D+/D-: node and label
    L([[0, y0], [0, r.cell - 120]]);
    if (n === 'RESET') {                                 // reset pull-up resistor (RRST) to VCC
      const px = pitch * 0.3, a = r.vcc + 6, b = r.gnd - 6;
      L([[px, r.vcc], [px, a]], COL.fet); dot(px, r.vcc, COL.vcc);
      x.strokeStyle = COL.fet; x.lineWidth = 1.6 * ui; x.beginPath(); x.moveTo(px, a);
      for (let i = 1; i <= 6; i++) x.lineTo(px + (i % 2 ? k * 0.3 : -k * 0.3), a + (b - a) * i / 6);
      x.lineTo(px, b); x.stroke(); L([[px, b], [px, b + 12], [0, b + 12]], COL.fet); dot(0, b + 12);
    }
    const what = { XTAL1: 'XTAL1 → osc. amplifier', XTAL2: 'XTAL2 ← osc. amplifier', RESET: 'RESET (pull-up)',
                   AREF: 'AREF → A/D', UCAP: 'UCAP 3.3 V reg. out', 'D+': 'D+ USB (pull-up, DETACH)', 'D-': 'D− USB' }[n] ?? n;
    label(what, r.cell - 60, COL.sig);
    return;
  }
  L([[0, y0], [0, r.cell - 95]]);                        // pad node
  // clamp diodes: node -> VCC ring, GND ring -> node
  const dx = -pitch * 0.28, pv = r.vcc + (r.gnd - r.vcc) * 0.3, gv = r.vcc + (r.gnd - r.vcc) * 0.7;
  L([[0, pv], [dx, pv]]); diode(dx, pv, r.vcc, COL.vcc); dot(0, pv);
  L([[0, gv], [dx, gv]]); diode(dx, r.gnd, gv, COL.gnd); dot(0, gv);
  // pull-up: VCC ring -> PMOS (source at the ring, gate from the pull-up logic) -> Rpu -> node
  const px = pitch * 0.3, fs = Math.min(k * 0.85, (r.gnd - r.vcc) * 0.22), pm = r.vcc + fs;
  dot(px, r.vcc, COL.vcc);
  drawFet(x, { t: 'p', x: px, y: pm, gr: true, fy: true, d: false }, fs, ui * 0.75);
  const rTop = pm + fs, rBot = r.gnd - 8;
  x.strokeStyle = COL.fet; x.lineWidth = 1.6 * ui; x.beginPath(); x.moveTo(px, rTop);
  for (let i = 1; i <= 6; i++) x.lineTo(px + (i % 2 ? k * 0.3 : -k * 0.3), rTop + (rBot - rTop) * i / 6);
  x.lineTo(px, rBot); x.stroke();
  L([[px, rBot], [px, r.gnd + 10], [0, r.gnd + 10]], COL.fet); dot(0, r.gnd + 10);
  // tri-state output driver, pointing at the pad, and the Schmitt-trigger input beside it
  const z = k * 0.8, ov = r.gnd + 22 + z;
  x.strokeStyle = COL.boxLine; x.fillStyle = COL.box; x.lineWidth = 1.6 * ui;
  x.beginPath(); x.moveTo(-z * 0.8, ov + z * 0.8); x.lineTo(z * 0.8, ov + z * 0.8); x.lineTo(0, ov - z * 0.6); x.closePath(); x.fill(); x.stroke();
  const iv = ov + z * 0.3;
  L([[0, ov - z * 0.6 - 4], [px, ov - z * 0.6 - 4], [px, iv - z * 0.7]]); dot(0, ov - z * 0.6 - 4);
  x.beginPath(); x.moveTo(px - z * 0.6, iv - z * 0.7); x.lineTo(px + z * 0.6, iv - z * 0.7); x.lineTo(px, iv + z * 0.6); x.closePath();
  x.fill(); x.stroke();
  L([[0, ov + z * 0.8], [0, r.cell - 95]]); L([[px, iv + z * 0.6], [px, r.cell - 95]]);
  label(n, r.cell - 60, COL.txt, 11);
}

// core: the datasheet block diagram's blocks on a grid, inside a data-bus ring; each block holds a transistor-level
// cell for its job (see cells.js). Block entries: [label, cell, column, row, column span, row span, cell options]
function drawCore(x, core, h, blocks) {
  const { line, text } = h, { x0, y0, x1, y1, cols, rows } = core, gw = (x1 - x0) / cols, gh = (y1 - y0) / rows, gap = 4;
  line([[x0 - 8, y0 - 8], [x1 + 8, y0 - 8], [x1 + 8, y1 + 8], [x0 - 8, y1 + 8], [x0 - 8, y0 - 8]], COL.sig, 3);
  if (core.bus) text(core.bus, (x0 + x1) / 2, y0 - 17, 9, 'center', COL.sig);
  for (const [label, ckt, c, rr, cw = 1, rh = 1, opt = {}] of core.blocks) {
    const r = { x: x0 + c * gw + gap / 2, y: y0 + rr * gh + gap / 2, w: cw * gw - gap, h: rh * gh - gap,
                l: label.replace(/\n/g, ' '), fill: label === 'AVR CPU' ? 'rgba(120,170,230,0.28)' : undefined };
    const o = { ckt, ...opt };
    drawBlock(x, r, o, h.ui); blocks.push({ r, o });
  }
}

// ------------------------------------------------------------------ 3D
export function buildCutaway(p, spec) {
  const pk = spec.pkg, b = p.body, g = new THREE.Group(), lay = padLayout(p, spec);
  const t = pk.frameT ?? 0.2, zf = pk.frameZ ?? 0;                // lead frame thickness and bottom
  // ghost of the moulded body
  const shell = slab(g, b.cx || 0, b.cy || 0, b.w, b.d, b.h, MAT.shell, pk.bodyZ ?? 0);
  shell.renderOrder = 2;
  const edges = new THREE.LineSegments(new THREE.EdgesGeometry(UNIT), MAT.ghost);
  edges.scale.copy(shell.scale); edges.position.copy(shell.position); g.add(edges);
  // die paddle(s)
  for (const pd of pk.paddles ?? [[0, 0, ...pk.paddle]]) slab(g, pd[0], pd[1], pd[2], pd[3], t, MAT.frame, pk.paddleZ ?? zf);
  // leads
  for (const q of lay.pins) {
    const out = { L: [-1, 0], R: [1, 0], T: [0, 1], B: [0, -1] }[q.side];
    if (pk.kind === 'qfn') {
      const [w, L] = pk.term, lr = 'LR'.includes(q.side);
      const cx = lr ? out[0] * (b.w / 2 - L / 2) : q.x, cy = lr ? q.y : out[1] * (b.d / 2 - L / 2);
      slab(g, cx, cy, lr ? L : w, lr ? w : L, t, MAT.frame, 0);
    } else {
      const lw = pk.leadW ?? 0.25, edge = [q.side === 'L' ? -b.w / 2 : q.side === 'R' ? b.w / 2 : q.x,
                                           q.side === 'T' ? b.d / 2 : q.side === 'B' ? -b.d / 2 : q.y];
      const zc = zf + t / 2;
      strip(g, [q.tip[0], q.tip[1], zc], [edge[0], edge[1], zc], pk.innerW ?? lw, t, MAT.frame);   // inner lead
      const knee = [edge[0] + out[0] * 0.25, edge[1] + out[1] * 0.25, zc];
      strip(g, [edge[0], edge[1], zc], knee, lw, t, MAT.frame);
      const foot = [q.x - out[0] * 0.25, q.y - out[1] * 0.25, 0.1];
      strip(g, knee, foot, lw, t, MAT.frame);                                                   // bend down to the foot
    }
  }
  // die, with the drawn circuit on its top face; each transistor-level block also gets its own sharper texture,
  // laid over the die just above its surface. Textures are shared by parts with the same value and footprint.
  const [dw, dd] = pk.die, dz = (pk.paddleZ ?? zf) + t + 0.02, dt = pk.dieT ?? 0.2;
  const key = p.value + '|' + p.package;
  if (!SKIN.has(key)) SKIN.set(key, dieSkin(spec, lay));
  const skin = SKIN.get(key), off = pk.dieAt ?? [0, 0];
  const die = new THREE.Mesh(UNIT, [MAT.dieSide, MAT.dieSide, skinMat(skin.tex), MAT.dieSide, MAT.dieSide, MAT.dieSide]);
  die.scale.set(dw, dt, dd); die.position.copy(V3(off[0], off[1], dz + dt / 2)); g.add(die);
  for (const ov of skin.overlays) {
    const { r } = ov, m = new THREE.Mesh(new THREE.PlaneGeometry(r.w / 1000 * dw, r.h / lay.Vd * dd), skinMat(ov.tex));
    m.rotation.x = -Math.PI / 2;
    m.position.copy(V3(off[0] + ((r.x + r.w / 2) / 1000 - 0.5) * dw, off[1] + (0.5 - (r.y + r.h / 2) / lay.Vd) * dd, dz + dt + 0.002));
    g.add(m);
  }
  // bond wires: die pad -> lead tip (or QFN terminal)
  const zt = dz + dt, loop = pk.loop ?? 0.22, r = pk.wireR ?? 0.016;
  const leadZ = (pk.kind === 'qfn' ? 0 : zf) + t;
  for (const q of lay.pins) {
    const a = V3(q.mm[0] + off[0], q.mm[1] + off[1], zt), e = V3(q.tip[0], q.tip[1], leadZ);
    const c1 = a.clone(); c1.y += loop;
    const c2 = a.clone().lerp(e, 0.55); c2.y = Math.max(a.y, e.y) + loop * 0.8;
    const curve = new THREE.CubicBezierCurve3(a, c1, c2, e);
    g.add(new THREE.Mesh(new THREE.TubeGeometry(curve, 20, r, 6, false), MAT.gold));
  }
  g.userData.canvas = skin.canvas;
  g.userData.overlays = skin.overlays;
  return g;
}

const SKIN = new Map();
function texture(canvas) {
  const tex = new THREE.CanvasTexture(canvas);
  tex.colorSpace = THREE.SRGBColorSpace; tex.anisotropy = 8;
  return tex;
}
function skinMat(tex) {
  return new THREE.MeshStandardMaterial({ map: tex, emissiveMap: tex, emissive: 0xffffff, emissiveIntensity: 0.55,
                                          roughness: 0.6, metalness: 0.1 });
}
function dieSkin(spec, lay) {
  const { canvas, blocks } = drawDie(spec, lay), ui = spec.pkg.ui ?? 1;
  const overlays = blocks.map(({ r, o }) => {
    // up to 12 px per die unit, at most 4096 px a side and about 4 Mpx per block
    const dpu = Math.min(12, 4096 / r.w, 4096 / r.h, Math.sqrt(4.2e6 / (r.w * r.h)));
    const c = document.createElement('canvas'); c.width = Math.ceil(r.w * dpu); c.height = Math.ceil(r.h * dpu);
    const x = c.getContext('2d'); x.scale(c.width / r.w, c.height / r.h); x.translate(-r.x, -r.y);
    x.fillStyle = COL.bg; x.fillRect(r.x, r.y, r.w, r.h);
    drawBlock(x, r, o, ui);
    return { r, canvas: c, tex: texture(c) };
  });
  return { canvas, tex: texture(canvas), overlays };
}
