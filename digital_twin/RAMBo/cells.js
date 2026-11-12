// Schematic symbols for the die drawings, and transistor-level circuits for the function blocks.
// The datasheets draw blocks such as the DAC, charge pump, oscillator, translator or the AVR's memories only as boxes,
// and the manufacturers do not publish the transistor designs behind them. Each block therefore gets the standard
// textbook circuit for its job (two-stage CMOS comparator, bandgap, R-string DAC, transmission-gate flip-flop, 6T SRAM
// cell, floating-gate NOR array...), and the specs say so. Cells are drawn in their own units (FET half-length 10)
// and scaled to fit their box; ports are cell nodes wired out to the box edge, where the die drawing's wires attach.

export const COL = { bg: '#1b222d', grid: '#212a37', seal: '#8b95a5', pad: '#cfd4dc', padTxt: '#0f141b', wire: '#c9d2dd',
                     pwr: '#ff9d5c', gnd: '#5fc2d6', sig: '#b8e07a', box: 'rgba(110,145,200,0.16)', boxLine: '#93abcf',
                     fet: '#f3dc92', txt: '#e9eef5', muted: '#9aa7b8', vcc: '#ff9d5c' };

// ------------------------------------------------------------------ symbols
export function drawFet(x, it, s, ui) {
  // enhancement MOSFET as the datasheets draw it: gate plate, broken channel, body tied to source, optional body diode;
  // fg adds a floating gate between the control gate and the channel (flash / EEPROM cells)
  x.save(); x.translate(it.x, it.y); x.scale((it.gr ? -1 : 1), it.fy ? -1 : 1);
  x.strokeStyle = COL.fet; x.fillStyle = COL.fet; x.lineWidth = 2.4 * ui;
  const L = (a, b, c, d) => { x.beginPath(); x.moveTo(a, b); x.lineTo(c, d); x.stroke(); };
  const gx = it.fg ? -s * 0.52 : -s * 0.42, cx = -s * 0.24;
  L(-s, 0, gx, 0);                                       // gate lead (terminal on the left)
  L(gx, -s * 0.45, gx, s * 0.45);                        // gate plate
  if (it.fg) L(-s * 0.36, -s * 0.5, -s * 0.36, s * 0.5); // floating gate
  for (const [a, b] of [[-0.55, -0.25], [-0.15, 0.15], [0.25, 0.55]]) L(cx, s * a, cx, s * b);   // channel
  L(cx, -s * 0.4, 0, -s * 0.4); L(0, -s * 0.4, 0, -s);   // drain
  L(cx, s * 0.4, 0, s * 0.4); L(0, s * 0.4, 0, s);       // source
  L(cx, 0, 0, 0); L(0, 0, 0, s * 0.4);                   // body to source
  const ah = s * 0.16, dir = it.t === 'n' ? -1 : 1;      // body arrow: into the channel for N, out for P
  x.beginPath(); x.moveTo(cx + (dir < 0 ? 0 : s * 0.2), 0);
  x.lineTo(cx + (dir < 0 ? ah : s * 0.2 - ah), -ah * 0.6); x.lineTo(cx + (dir < 0 ? ah : s * 0.2 - ah), ah * 0.6); x.fill();
  if (it.t === 'p') { x.beginPath(); x.arc(gx - s * 0.09, 0, s * 0.08, 0, 7); x.stroke(); }
  if (it.d !== false) {                                  // body diode, cathode at the drain
    const dx = s * 0.38;
    L(0, -s * 0.72, dx, -s * 0.72); L(dx, -s * 0.72, dx, s * 0.72); L(dx, s * 0.72, 0, s * 0.72);
    const h = s * 0.16;
    x.beginPath(); x.moveTo(dx, -h); x.lineTo(dx - h, h * 0.8); x.lineTo(dx + h, h * 0.8); x.closePath(); x.fill();
    L(dx - h, -h, dx + h, -h);
  }
  x.restore();
  if (it.l) {
    x.save(); x.fillStyle = COL.muted; x.font = `${(it.fs ?? 11) * ui}px system-ui, sans-serif`;
    x.textAlign = it.gr ? 'right' : 'left'; x.textBaseline = 'middle';
    x.fillText(it.l, it.x + (it.gr ? -1 : 1) * s * 0.55, it.y - s * 0.75); x.restore();
  }
}

export function drawAmp(x, it, s, ui, text) {
  const ang = { r: 0, d: 90, l: 180, u: -90 }[it.dir || 'r'] * Math.PI / 180;
  x.save(); x.translate(it.x, it.y); x.rotate(ang);
  x.strokeStyle = COL.boxLine; x.fillStyle = COL.box; x.lineWidth = 2.2 * ui;
  const h = it.t === 'amp' ? s * 0.8 : s * 0.6;
  x.beginPath(); x.moveTo(-s * 0.7, -h); x.lineTo(s * 0.7, 0); x.lineTo(-s * 0.7, h); x.closePath(); x.fill(); x.stroke();
  const L = (a, b, c, d) => { x.beginPath(); x.moveTo(a, b); x.lineTo(c, d); x.stroke(); };
  L(s * 0.7, 0, s, 0);                                   // output lead
  if (it.t === 'amp') {
    L(-s, -s * 0.45, -s * 0.7, -s * 0.45); L(-s, s * 0.45, -s * 0.7, s * 0.45);
    x.fillStyle = COL.txt; x.font = `${s * 0.42}px system-ui`; x.textAlign = 'center'; x.textBaseline = 'middle';
    const [ta, tb] = it.inv ? ['+', '−'] : ['−', '+'];
    x.fillText(ta, -s * 0.48, -s * 0.42); x.fillText(tb, -s * 0.48, s * 0.42);
  } else {
    L(-s, 0, -s * 0.7, 0);
    if (it.t === 'inv') { x.beginPath(); x.arc(s * 0.78, 0, s * 0.08, 0, 7); x.stroke(); }
    if (it.t === 'st') {                                 // Schmitt trigger glyph
      x.beginPath(); x.moveTo(-s * 0.35, s * 0.15); x.lineTo(-s * 0.05, s * 0.15); x.lineTo(-s * 0.05, -s * 0.15);
      x.moveTo(-s * 0.2, s * 0.15); x.lineTo(-s * 0.2, -s * 0.15); x.lineTo(s * 0.1, -s * 0.15); x.stroke();
    }
    if (it.en) L(0, -s * 0.5, 0, -s * 0.36);             // tri-state enable
  }
  x.restore();
  if (it.l) text(it.l, it.x + (it.lx ?? 0), it.y + (it.ly ?? s * 1.05), it.fs ?? 11, 'center', COL.muted);
}

export function drawTwo(x, it, a, b, ui, text) {
  const dx = b[0] - a[0], dy = b[1] - a[1], len = Math.hypot(dx, dy), ang = Math.atan2(dy, dx);
  x.save(); x.translate(a[0], a[1]); x.rotate(ang);
  x.strokeStyle = it.t === 'coil' ? COL.sig : COL.fet; x.fillStyle = x.strokeStyle; x.lineWidth = 2.2 * ui;
  const L = (p, q, r, s) => { x.beginPath(); x.moveTo(p, q); x.lineTo(r, s); x.stroke(); };
  const m = len / 2, z = Math.min(len * 0.32, it.sz ?? 30);
  L(0, 0, m - z, 0); L(m + z, 0, len, 0);
  if (it.t === 'res') {
    x.beginPath(); x.moveTo(m - z, 0);
    for (let i = 1; i <= 6; i++) x.lineTo(m - z + (2 * z) * i / 6 - z / 6, (i % 2 ? -1 : 1) * z * 0.3);
    x.lineTo(m + z, 0); x.stroke();
  } else if (it.t === 'cap') {
    L(m - z * 0.2, -z * 0.6, m - z * 0.2, z * 0.6); L(m + z * 0.2, -z * 0.6, m + z * 0.2, z * 0.6);
    L(m - z, 0, m - z * 0.2, 0); L(m + z * 0.2, 0, m + z, 0);
  } else if (it.t === 'dio') {                           // anode at a, cathode at b
    x.beginPath(); x.moveTo(m - z * 0.5, -z * 0.5); x.lineTo(m + z * 0.4, 0); x.lineTo(m - z * 0.5, z * 0.5); x.closePath(); x.fill();
    L(m + z * 0.4, -z * 0.5, m + z * 0.4, z * 0.5); L(m - z, 0, m - z * 0.5, 0); L(m + z * 0.4, 0, m + z, 0);
  } else if (it.t === 'coil') {
    x.beginPath(); x.moveTo(m - z, 0);
    for (let i = 0; i < 4; i++) x.arc(m - z + z / 4 + i * z / 2, 0, z / 4, Math.PI, 0, false);
    x.stroke();
  }
  x.restore();
  if (it.l) text(it.l, (a[0] + b[0]) / 2 + (it.lx ?? 0), (a[1] + b[1]) / 2 + (it.ly ?? -22), it.fs ?? 11, 'center', COL.muted);
}

// ------------------------------------------------------------------ cell drawing kit (cell units, FET half-length S)
const S = 10;
function kit(x, mx) {
  const k = { x };
  k.w = (pts, col = COL.wire, lw = 1.1) => {
    x.strokeStyle = col; x.lineWidth = lw; x.beginPath();
    pts.forEach((p, i) => (i ? x.lineTo(p[0], p[1]) : x.moveTo(p[0], p[1]))); x.stroke();
  };
  k.dot = (p, col = COL.wire) => { x.fillStyle = col; x.beginPath(); x.arc(p[0], p[1], 1.5, 0, 7); x.fill(); };
  // text stays readable in a mirrored cell; a leading "~" draws an overbar ("~CK" = CK inverted)
  k.t = (s, u, v, size = 5, align = 'center', col = COL.muted, weight = '') => {
    s = String(s); const bar = s[0] === '~'; if (bar) s = s.slice(1);
    const al = mx ? ({ left: 'right', right: 'left' }[align] ?? align) : align;
    x.save(); x.translate(u, v); if (mx) x.scale(-1, 1);
    x.fillStyle = col; x.font = `${weight} ${size}px system-ui, sans-serif`; x.textAlign = al; x.textBaseline = 'middle';
    const lines = s.split('\n');
    lines.forEach((l, i) => x.fillText(l, 0, (i - (lines.length - 1) / 2) * size * 1.15));
    if (bar) {
      const w = x.measureText(s).width, x0 = al === 'left' ? 0 : al === 'right' ? -w : -w / 2;
      x.strokeStyle = col; x.lineWidth = size * 0.09; x.beginPath(); x.moveTo(x0, -size * 0.6); x.lineTo(x0 + w, -size * 0.6); x.stroke();
    }
    x.restore();
  };
  // MOSFET at (u, v); rot turns it (90: channel horizontal, gate on top). Returns terminal points d, s, g.
  k.fet = (t, u, v, o = {}) => {
    const s = o.s ?? S, a = (o.rot ?? 0) * Math.PI / 180, c = Math.round(Math.cos(a) * 1e6) / 1e6, sn = Math.round(Math.sin(a) * 1e6) / 1e6;
    x.save(); x.translate(u, v); x.rotate(a);
    drawFet(x, { t, x: 0, y: 0, gr: o.gr, fy: o.fy, d: o.d ?? false, fg: o.fg }, s, 0.5);
    x.restore();
    const R = (dx, dy) => [u + dx * c - dy * sn, v + dx * sn + dy * c], fy = o.fy ? -1 : 1, gs = o.gr ? 1 : -1;
    const T = { d: R(0, -s * fy), s: R(0, s * fy), g: R(gs * s, 0) };
    if (o.gl) {                                          // signal name on an unwired gate
      const dx = (T.g[0] - u) / s, dy = (T.g[1] - v) / s;
      if (Math.abs(dx) > 0.5) k.t(o.gl, T.g[0] + dx * 1.2, T.g[1], 4.5, dx < 0 ? 'right' : 'left');
      else k.t(o.gl, T.g[0], T.g[1] + dy * 3.5, 4.5);
    }
    return T;
  };
  k.n = (u, v, o) => k.fet('n', u, v, o);
  k.p = (u, v, o) => k.fet('p', u, v, o);
  k.vdd = (p, l) => { k.w([[p[0] - 5, p[1]], [p[0] + 5, p[1]]], COL.pwr, 1.4); if (l) k.t(l, p[0], p[1] - 3.5, 4.5, 'center', COL.pwr); };
  k.gnd = p => {
    const [u, v] = p; k.w([[u, v], [u, v + 3]], COL.gnd);
    for (const [w, o] of [[9, 3], [5.5, 5], [2, 7]]) k.w([[u - w / 2, v + o], [u + w / 2, v + o]], COL.gnd);
  };
  const two = t => (a, b, o = {}) =>
    drawTwo(x, { t, sz: o.sz ?? 6, l: o.l, lx: o.lx ?? 0, ly: o.ly ?? -6, fs: o.fs ?? 4.5 }, a, b, 0.5, k.t);
  k.res = two('res'); k.cap = two('cap'); k.dio = two('dio');
  k.amp = (u, v, s, o = {}) => drawAmp(x, { t: 'amp', x: u, y: v, dir: o.dir }, s, 0.5, k.t);
  // vertical PNP (substrate type: base and collector to ground), emitter on top
  k.pnp = (u, v, l) => {
    x.strokeStyle = COL.fet; x.fillStyle = COL.fet; x.lineWidth = 1.2;
    const L = (a, b, c, d) => { x.beginPath(); x.moveTo(a, b); x.lineTo(c, d); x.stroke(); };
    const bx = u - 4;
    L(u - 10, v, bx, v); L(bx, v - 5, bx, v + 5);
    L(bx, v - 2.5, u, v - 6); L(u, v - 6, u, v - 10);
    L(bx, v + 2.5, u, v + 6); L(u, v + 6, u, v + 10);
    const d = [-0.7526, 0.6585], n = [-d[1], d[0]], tip = [u - 3.2, v - 3.2], b = [tip[0] - d[0] * 2.2, tip[1] - d[1] * 2.2];
    x.beginPath(); x.moveTo(...tip); x.lineTo(b[0] + n[0] * 1.1, b[1] + n[1] * 1.1); x.lineTo(b[0] - n[0] * 1.1, b[1] - n[1] * 1.1); x.fill();
    k.w([[u - 10, v], [u - 10, v + 14], [u, v + 14]]); k.w([[u, v + 10], [u, v + 14]]); k.gnd([u, v + 14]);
    if (l) k.t(l, u + 3, v + 1, 4.5, 'left');
    return { e: [u, v - 10] };
  };
  // CMOS inverter centred on its output node; rev puts the input on the right
  k.inv = (u, v, o = {}) => {
    const P = k.p(u, v - 14, { fy: true, gr: o.rev }), N = k.n(u, v + 14, { gr: o.rev });
    k.w([P.d, N.d]); k.w([P.g, N.g]);
    if (o.sup !== false) { k.vdd(P.s, o.vl); k.gnd(N.s); }
    return { i: [P.g[0], v], o: [u, v], P, N };
  };
  // transmission gate between a (left) and b (right): NMOS gate on top, PMOS gate below
  k.tg = (u, v, o = {}) => {
    k.fet('n', u, v - 7, { rot: 90 }); k.fet('p', u, v + 7, { rot: -90 });
    k.w([[u - 10, v - 7], [u - 10, v + 7]]); k.w([[u + 10, v - 7], [u + 10, v + 7]]);
    if (o.n) k.t(o.n, u, v - 20, 4.5); if (o.p) k.t(o.p, u, v + 20.5, 4.5);
    return { a: [u - 10, v], b: [u + 10, v] };
  };
  k.sub = (name, dx, dy, o = {}) => { x.save(); x.translate(dx, dy); CELLS[name].draw(k, o); x.restore(); };
  return k;
}

// ------------------------------------------------------------------ cells
// ports: name -> [u, v, side]; the box edge on that side is where outside wires attach
const CELLS = {
  // two-stage CMOS comparator: NMOS input pair with PMOS mirror load, tail source, common-source output stage
  cmp: { w: 140, h: 112, ports: { a: [0, 50, 'l'], b: [0, 108, 'l'], o: [140, 40, 'r'] },
    draw(k, o) {
      const M3 = k.p(40, 20, { fy: true, gr: true }), M4 = k.p(80, 20, { fy: true });
      k.vdd(M3.s); k.vdd(M4.s);
      k.w([M3.g, M4.g]); k.w([[40, 34], [60, 34], [60, 20]]); k.dot([60, 20]); k.dot([40, 34]);
      const M1 = k.n(40, 50), M2 = k.n(80, 50, { gr: true });
      k.w([M3.d, M1.d]); k.w([M4.d, M2.d]);
      k.w([M1.s, [40, 64], [80, 64], M2.s]); k.dot([60, 64]);
      const M5 = k.n(60, 80, { gl: 'Vb' }); k.w([[60, 64], M5.d]); k.gnd(M5.s);
      k.w([[0, 50], M1.g]); k.w([[0, 108], [94, 108], [94, 50], M2.g]);
      const M6 = k.p(120, 20, { fy: true }), M7 = k.n(120, 80, { gl: 'Vb' });
      k.vdd(M6.s); k.gnd(M7.s);
      k.w([[80, 36], [104, 36], [104, 20], M6.g]); k.dot([80, 36]);
      k.w([M6.d, M7.d]); k.dot([120, 40]); k.w([[120, 40], [140, 40]]);
      k.t('−  ' + (o.a ?? ''), 3, 45, 5, 'left', COL.txt); k.t('+  ' + (o.b ?? ''), 3, 103, 5, 'left', COL.txt);
      if (o.out) k.t(o.out, 137, 35, 4.5, 'right');
    } },

  // linear regulator: 5-transistor error amplifier, PMOS pass device, feedback divider
  vreg: { w: 150, h: 122, ports: { out: [150, 62, 'r'] },
    draw(k, o) {
      const M3 = k.p(30, 20, { fy: true, gr: true }), M4 = k.p(70, 20, { fy: true });
      k.vdd(M3.s); k.vdd(M4.s);
      k.w([M3.g, M4.g]); k.w([[30, 34], [50, 34], [50, 20]]); k.dot([50, 20]); k.dot([30, 34]);
      const M1 = k.n(30, 50, { gl: o.ref ?? 'VREF' }), M2 = k.n(70, 50, { gr: true });
      k.w([M3.d, M1.d]); k.w([M4.d, M2.d]);
      k.w([M1.s, [30, 64], [70, 64], M2.s]); k.dot([50, 64]);
      const M5 = k.n(50, 80, { gl: 'Vb' }); k.w([[50, 64], M5.d]); k.gnd(M5.s);
      const MP = k.p(115, 20, { fy: true }); k.vdd(MP.s, o.vin ?? 'VIN');
      k.w([[70, 36], [100, 36], [100, 20], MP.g]); k.dot([70, 36]);
      k.w([MP.d, [115, 62]]); k.dot([115, 62]); k.w([[115, 62], [150, 62]]);
      k.res([115, 62], [115, 88], { l: 'R1', lx: 8, ly: 0 }); k.dot([115, 88]);
      k.res([115, 88], [115, 112], { l: 'R2', lx: 8, ly: 0 }); k.gnd([115, 112]);
      k.w([[115, 88], [86, 88], [86, 50], M2.g]);
      k.t(o.out ?? 'VOUT', 146, 57, 4.5, 'right'); k.t('pass', 125, 20, 4.5, 'left');
    } },

  // bandgap: self-biased PTAT core (PMOS mirror, NMOS pair, PNPs 1x and Nx with R1), output branch R2 + PNP
  bandgap: { w: 150, h: 125, ports: { out: [150, 44, 'r'] },
    draw(k, o) {
      const Ma = k.p(30, 20, { fy: true, gr: true }), Mb = k.p(70, 20, { fy: true }), Mc = k.p(115, 20, { fy: true, gl: 'PB' });
      for (const m of [Ma, Mb, Mc]) k.vdd(m.s);
      k.w([Ma.g, Mb.g]); k.t('PB', 50, 16, 4.5);
      k.w([[70, 36], [54, 36], [54, 20]]); k.dot([54, 20]); k.dot([70, 36]);
      const M1 = k.n(30, 50, { gr: true }), M2 = k.n(70, 50);
      k.w([Ma.d, M1.d]); k.w([Mb.d, M2.d]); k.w([M1.g, M2.g]);
      k.w([[30, 36], [46, 36], [46, 50]]); k.dot([46, 50]); k.dot([30, 36]);
      const Q1 = k.pnp(30, 100, '1×'), Q2 = k.pnp(70, 100, 'N×'), Q3 = k.pnp(115, 100, 'N×');
      k.w([M1.s, Q1.e]);
      k.res([70, 60], [70, 90], { l: 'R1', lx: 8, ly: 0 });
      k.w([Mc.d, [115, 44]]); k.dot([115, 44]); k.w([[115, 44], [150, 44]]);
      k.res([115, 44], [115, 90], { l: 'R2', lx: 8, ly: 0 });
      k.t(o.out ?? 'VBG', 146, 39, 4.5, 'right');
    } },

  // ring oscillator: three inverters in a loop
  ring: { w: 150, h: 88, ports: { o: [150, 40, 'r'] },
    draw(k) {
      const I = [25, 65, 105].map(u => k.inv(u, 40));
      k.w([I[0].o, I[1].i]); k.w([I[1].o, I[2].i]);
      k.w([I[2].o, [128, 40], [128, 80], [8, 80], [8, 40], I[0].i]); k.dot([128, 40]); k.w([[128, 40], [150, 40]]);
    } },

  // relaxation oscillator: mirrored set current charges C; two inverters detect the threshold and fire the reset switch
  relax: { w: 180, h: 100, ports: { set: [0, 44, 'l'], ramp: [0, 62, 'l'], o: [180, 50, 'r'] },
    draw(k, o) {
      const Ma = k.p(30, 20, { fy: true, gr: true }), Mb = k.p(70, 20, { fy: true });
      k.vdd(Ma.s); k.vdd(Mb.s);
      k.w([Ma.g, Mb.g]); k.w([[30, 36], [50, 36], [50, 20]]); k.dot([50, 20]); k.dot([30, 36]);
      k.w([Ma.d, [30, 44], [0, 44]]); k.t(o.set ?? 'Ibias', 2, 40, 4.5, 'left');
      k.w([Mb.d, [70, 62]]); k.dot([70, 50]);
      if (!o.ports || o.ports.includes('ramp')) { k.w([[70, 62], [0, 62]]); k.dot([70, 62]); k.t('ramp', 2, 58, 4.5, 'left'); }
      k.cap([70, 62], [70, 86], { l: 'C', lx: 7, ly: 0 }); k.gnd([70, 86]);
      const Mr = k.n(98, 70, { gr: true }); k.gnd(Mr.s);
      k.w([[70, 50], [98, 50], Mr.d]); k.dot([98, 50]);
      const I1 = k.inv(125, 50), I2 = k.inv(155, 50);
      k.w([[98, 50], I1.i]); k.w([I1.o, I2.i]);
      k.w([I2.o, [180, 50]]); k.dot([168, 50]);
      k.w([[168, 50], [168, 94], [108, 94], Mr.g]);
    } },

  // crystal oscillator amplifier (Pierce): inverter biased by a feedback resistor; the crystal sits between the pins
  pierce: { w: 110, h: 92, ports: { x1: [0, 40, 'l'], x2: [110, 40, 'r'] },
    draw(k) {
      const I = k.inv(55, 40);
      k.w([[0, 40], I.i]); k.dot([30, 40]);
      k.w([I.o, [110, 40]]); k.dot([80, 40]);
      k.w([[30, 40], [30, 82]]); k.res([30, 82], [80, 82], { l: 'Rf', ly: 6 }); k.w([[80, 82], [80, 40]]);
      k.t('XTAL1', 2, 35, 4.5, 'left'); k.t('XTAL2', 108, 35, 4.5, 'right');
    } },

  // positive-edge D flip-flop: transmission-gate master and slave latches, each with a feedback inverter
  dff: { w: 160, h: 146, ports: { d: [0, 40, 'l'], q: [160, 40, 'r'] },
    draw(k) {
      const T1 = k.tg(22, 40, { n: '~CK', p: 'CK' }), I1 = k.inv(55, 40);
      const T3 = k.tg(88, 40, { n: 'CK', p: '~CK' }), I3 = k.inv(121, 40);
      k.w([[0, 40], T1.a]); k.w([T1.b, I1.i]); k.w([I1.o, T3.a]); k.w([T3.b, I3.i]); k.w([I3.o, [160, 40]]);
      const I2 = k.inv(58, 112, { rev: true }), T2 = k.tg(36, 112, { n: 'CK', p: '~CK' });
      k.w([[68, 40], I2.i]); k.dot([68, 40]); k.w([I2.o, T2.b]); k.w([T2.a, [26, 78], [40, 78], [40, 40]]); k.dot([40, 40]);
      const I4 = k.inv(124, 112, { rev: true }), T4 = k.tg(102, 112, { n: '~CK', p: 'CK' });
      k.w([[134, 40], I4.i]); k.dot([134, 40]); k.w([I4.o, T4.b]); k.w([T4.a, [92, 78], [106, 78], [106, 40]]); k.dot([106, 40]);
      k.t('D', 2, 35, 5.5, 'left', COL.txt); k.t('Q', 158, 35, 5.5, 'right', COL.txt);
    } },

  // 6-transistor SRAM cells, 2 x 2: cross-coupled inverters with access transistors to BL / ~BL on word line WL
  sram: { w: 184, h: 152,
    draw(k) {
      const us = [50, 134], vs = [42, 112];
      vs.forEach((v, i) => { k.w([[4, v - 30], [180, v - 30]]); k.t('WL' + i, 2, v - 33.5, 4.5, 'left'); });
      for (const u of us) {
        k.w([[u - 36, 4], [u - 36, 142]]); k.w([[u + 36, 4], [u + 36, 142]]);
        k.t('BL', u - 36, 147, 4.5); k.t('~BL', u + 36, 147, 4.5);
      }
      for (const u of us) for (const v of vs) {
        const P1 = k.p(u - 16, v - 14, { fy: true, gr: true }), N1 = k.n(u - 16, v + 14, { gr: true });
        const P2 = k.p(u + 16, v - 14, { fy: true }), N2 = k.n(u + 16, v + 14);
        k.vdd(P1.s); k.vdd(P2.s); k.gnd(N1.s); k.gnd(N2.s);
        k.w([P1.d, N1.d]); k.w([P2.d, N2.d]); k.w([P1.g, N1.g]); k.w([P2.g, N2.g]);
        k.w([[u - 16, v + 2], [u + 6, v + 2]]); k.dot([u - 16, v + 2]); k.dot([u + 6, v + 2]);
        k.w([[u + 16, v - 2], [u - 6, v - 2]]); k.dot([u + 16, v - 2]); k.dot([u - 6, v - 2]);
        k.n(u - 26, v, { rot: 90 }); k.n(u + 26, v, { rot: 90 });
        for (const a of [u - 26, u + 26]) { k.w([[a, v - 10], [a, v - 30]]); k.dot([a, v - 30]); }
        k.dot([u - 36, v]); k.dot([u + 36, v]); k.dot([u - 16, v]); k.dot([u + 16, v]);
      }
    } },

  // NOR flash, 3 x 3 floating-gate transistors: drain to bit line, control gate to word line, source to source line
  flash: { w: 166, h: 154,
    draw(k) {
      const xs = [32, 82, 132], ys = [34, 78, 122];
      ys.forEach((y, i) => {
        k.w([[4, y - 16], [162, y - 16]]); k.t('WL' + i, 2, y - 19.5, 4.5, 'left');
        k.w([[24, y + 15], [162, y + 15]], COL.gnd); k.t('SL', 22, y + 15, 4.5, 'right', COL.gnd);
      });
      xs.forEach((x, j) => { k.w([[x + 14, 6], [x + 14, 146]]); k.t('BL' + j, x + 14, 150, 4.5); });
      for (const y of ys) for (const x of xs) {
        const T = k.n(x, y, { fg: true });
        k.w([T.d, [x + 14, y - 10]]); k.dot([x + 14, y - 10]);
        k.w([T.g, [x - 10, y - 16]]); k.dot([x - 10, y - 16]);
        k.w([T.s, [x, y + 15]]); k.dot([x, y + 15], COL.gnd);
      }
    } },

  // EEPROM, 2 x 2 two-transistor cells: select transistor in series with a floating-gate (FLOTOX) transistor
  eeprom: { w: 160, h: 150,
    draw(k) {
      const xs = [40, 110], ys = [10, 76];
      xs.forEach((x, j) => { k.w([[x + 16, 4], [x + 16, 142]]); k.t('BL' + j, x + 16, 147, 4.5); });
      ys.forEach((y0, i) => {
        k.w([[20, y0 + 48], [150, y0 + 48]], COL.gnd); k.t('SL', 18, y0 + 48, 4.5, 'right', COL.gnd);
        for (const x of xs) {
          const Ts = k.n(x, y0 + 14, { gl: 'SG' + i }), Tf = k.n(x, y0 + 34, { fg: true, gl: 'CG' + i });
          k.w([Ts.d, [x + 16, y0 + 4]]); k.dot([x + 16, y0 + 4]);
          k.w([Ts.s, Tf.d]); k.w([Tf.s, [x, y0 + 48]]); k.dot([x, y0 + 48], COL.gnd);
        }
      });
    } },

  // NOR ROM / decoder plane: PMOS pull-ups on the bit lines, an NMOS wherever a row pulls its bit line low
  rom: { w: 178, h: 186,
    draw(k, o) {
      const bits = o.bits ?? [[1, 0, 1, 0], [0, 1, 1, 0], [1, 1, 0, 1], [0, 0, 1, 1], [1, 0, 0, 1]];
      const cols = bits[0].length, bx = j => 44 + 34 * j, wy = i => 46 + 24 * i, bottom = wy(bits.length - 1) + 24;
      for (let j = 0; j < cols; j++) {
        const P = k.p(bx(j), 18, { fy: true }); k.vdd(P.s);
        k.w([P.g, [P.g[0], 24]]); k.gnd([P.g[0], 24]);
        k.w([P.d, [bx(j), bottom]]);
        k.t(o.cols?.[j] ?? '~D' + (cols - 1 - j), bx(j), bottom + 5, 4.5, 'center', COL.txt);
      }
      bits.forEach((row, i) => {
        k.w([[6, wy(i)], [bx(cols - 1) + 26, wy(i)]]); k.t(o.rows?.[i] ?? 'S' + i, 4, wy(i) - 3.5, 4.5, 'left');
        row.forEach((b, j) => {
          if (!b) return;
          const u = bx(j) + 10, v = wy(i) + 10;
          k.n(u, v, { rot: 90 }); k.dot([u, wy(i)]); k.dot([bx(j), v]); k.gnd([u + 10, v]);
        });
      });
      if (o.note) k.t(o.note, 6, bottom + 14, 4.5, 'left');
    } },

  // mirror-adder carry stage: Cout = majority(A, B, Ci), built as the complementary PMOS / NMOS networks + inverter
  adder: { w: 150, h: 118, ports: { co: [150, 60, 'r'] },
    draw(k) {
      const P1 = k.p(30, 22, { fy: true, gl: 'A' }), P2 = k.p(55, 22, { fy: true, gl: 'B' });
      const P4 = k.p(90, 22, { fy: true, gl: 'A' }), P5 = k.p(90, 46, { fy: true, gl: 'B' });
      for (const m of [P1, P2, P4]) k.vdd(m.s);
      k.w([P1.d, [30, 34], [55, 34], P2.d]); k.dot([42, 34]);
      const P3 = k.p(42, 46, { fy: true, gl: 'Ci' }); k.w([[42, 34], P3.s]); k.w([P4.d, P5.s]);
      k.w([P3.d, [42, 60], [108, 60]]); k.w([P5.d, [90, 60]]); k.dot([42, 60]); k.dot([90, 60]);
      const N3 = k.n(42, 74, { gl: 'Ci' }), N1 = k.n(30, 98, { gl: 'A' }), N2 = k.n(55, 98, { gl: 'B' });
      const N4 = k.n(90, 74, { gl: 'A' }), N5 = k.n(90, 98, { gl: 'B' });
      k.w([[42, 60], N3.d]); k.w([N3.s, [42, 88]]); k.w([N1.d, [30, 88], [55, 88], N2.d]); k.dot([42, 88]);
      k.w([[90, 60], N4.d]); k.w([N4.s, N5.d]);
      for (const m of [N1, N2, N5]) k.gnd(m.s);
      const I = k.inv(118, 60); k.w([I.o, [150, 60]]);
      k.t('~Cout', 66, 55, 4.5); k.t('Cout', 147, 55, 4.5, 'right', COL.txt);
    } },

  // static CMOS NAND2 followed by an inverter (an AND gate)
  nand: { w: 130, h: 85, ports: { o: [130, 45, 'r'] },
    draw(k, o) {
      const [a, b] = o.in ?? ['A', 'B'];
      const PA = k.p(20, 20, { fy: true, gl: a }), PB = k.p(50, 20, { fy: true, gl: b });
      k.vdd(PA.s); k.vdd(PB.s);
      k.w([PA.d, [20, 33], [50, 33], PB.d]);
      const NA = k.n(50, 43, { gl: a }), NB = k.n(50, 63, { gl: b }); k.gnd(NB.s);
      k.w([[50, 33], NA.d]); k.w([NA.s, NB.d]); k.dot([50, 33]);
      const I = k.inv(95, 45); k.w([[50, 33], [85, 33]]); k.dot([85, 33]); k.w([I.o, [130, 45]]);
      k.t(o.out ?? 'Y', 127, 40, 4.5, 'right', COL.txt);
    } },

  // SR latch from two cross-coupled CMOS NOR2 gates
  latch: { w: 150, h: 88, ports: { q: [150, 54, 'r'] },
    draw(k) {
      const nor = (u, A, B) => {
        const PA = k.p(u, 20, { fy: true, gl: A }), PB = k.p(u, 40, { fy: true, gl: B });
        k.vdd(PA.s);
        const NA = k.n(u, 66, { gl: A }), NB = k.n(u + 22, 66, { gl: B });
        k.w([PB.d, [u, 54], [u + 22, 54], NB.d]); k.w([[u, 54], NA.d]); k.dot([u, 54]);
        k.gnd(NA.s); k.gnd(NB.s);
        return [u + 22, 54];
      };
      const qb = nor(22, 'S', 'Q'), q = nor(96, 'R', '~Q');
      k.w([qb, [62, 54]]); k.t('~Q', 64, 54, 5, 'left', COL.txt);
      k.w([q, [150, 54]]); k.dot(q); k.t('Q', 140, 49, 5, 'center', COL.txt);
    } },

  // resistor-string DAC: taps of a string from REF, NMOS switches onto the output (4 of the taps drawn)
  dac: { w: 100, h: 126, ports: { ref: [6, 126, 'b'], out: [100, 60, 'r'] },
    draw(k) {
      k.w([[6, 126], [6, 4], [20, 4]]); k.t('REF', 23, 3, 4.5, 'left');
      const taps = [24, 48, 72, 96];
      let y = 4;
      for (const t of taps) { k.res([20, y], [20, t]); y = t; }
      k.res([20, 96], [20, 114]); k.gnd([20, 114]);
      taps.forEach((t, i) => {
        k.dot([20, t]); k.w([[20, t], [30, t]]);
        k.n(40, t, { rot: 90, gl: 'S' + (3 - i) });
        k.w([[50, t], [62, t]]); k.dot([62, t]);
      });
      k.w([[62, 24], [62, 96]]); k.w([[62, 60], [100, 60]]);
      k.t('4 of 16 taps', 96, 104, 4.5, 'right');
    } },

  // charge pump: an inverter swings CP1 between GND and VREG; diodes lift CP2 from VBB and pass the charge to VCP
  chargepump: { w: 110, h: 160, ports: { cp1: [0, 40, 'l'], cp2: [0, 100, 'l'], vcp: [70, 160, 'b'] },
    draw(k) {
      const I = k.inv(40, 40, { rev: true, vl: 'VREG' });
      k.w([I.i, [62, 40]]); k.t('OSC', 64, 40, 4.5, 'left');
      k.w([I.o, [0, 40]]);
      k.vdd([70, 72], 'VBB');
      k.dio([70, 72], [70, 100]); k.w([[0, 100], [70, 100]]); k.dot([70, 100]);
      k.dio([70, 100], [70, 130]); k.w([[70, 130], [70, 160]]); k.dot([70, 130]);
      k.t('CP1', 3, 35, 4.5, 'left'); k.t('CP2', 3, 95, 4.5, 'left'); k.t('VCP', 74, 145, 4.5, 'left');
    } },

  // gate drivers (CMOS inverters) for the bridge FETs, flanked by the over-current comparators
  gatedrv: { w: 640, h: 118,
    draw(k, o) {
      k.sub('cmp', 0, 0, { a: 'Vth', b: 'VDS', out: 'fault' });
      const names = o.names ?? [], hs = o.hs ?? [], ret = o.ret ?? [];
      names.forEach((n, i) => {
        const u = 170 + 42 * i, v = 50, I = k.inv(u, v, { sup: false });
        k.vdd(I.P.s, hs[i] ? 'VCP' : 'VREG');
        if (hs[i]) { k.w([[u - 5, I.N.s[1]], [u + 5, I.N.s[1]]], COL.wire, 1.4); k.t(ret[i] ?? 'OUT', u, I.N.s[1] + 4, 4.5); }
        else k.gnd(I.N.s);
        k.w([I.o, [u + 9, v], [u + 9, 12]]); k.dot([u + 9, 12]);
        k.t('→ ' + n, u + 9, 6, 4.5, 'center', COL.txt);
      });
      k.t('driver inputs from the PWM latches and control logic', 320, 113, 4.5);
      k.sub('cmp', 500, 0, { a: 'Vth', b: 'VDS', out: 'fault' });
    } },

  // passive network of a type III compensator (component values are not published)
  rc3: { w: 124, h: 72, ports: { in: [0, 24, 'l'], out: [124, 24, 'r'] },
    draw(k) {
      k.w([[0, 24], [10, 24]]); k.res([10, 24], [55, 24], { l: 'R1', ly: 6 });
      k.w([[10, 24], [10, 8]]); k.res([10, 8], [32, 8], { l: 'R3', ly: -5 }); k.cap([32, 8], [55, 8], { l: 'C3', ly: -5 });
      k.w([[55, 8], [55, 24]]); k.dot([10, 24]); k.dot([55, 24]);
      k.w([[55, 24], [124, 24]]);
      k.cap([80, 24], [80, 54], { l: 'C1', lx: -6, ly: 0 }); k.gnd([80, 54]); k.dot([80, 24]);
      k.res([104, 24], [104, 44], { l: 'R2', lx: 7, ly: 0 }); k.cap([104, 44], [104, 62], { l: 'C2', lx: 7, ly: 0 });
      k.gnd([104, 62]); k.dot([104, 24]);
    } },

  // charge-redistribution SAR converter front end: binary-weighted capacitor array, switches, comparator
  sar: { w: 165, h: 95,
    draw(k) {
      const xs = [24, 44, 64, 84, 104], cs = ['8C', '4C', '2C', 'C', 'C'];
      k.w([[24, 20], [128, 20]]);
      xs.forEach((x, i) => {
        k.dot([x, 20]); k.cap([x, 20], [x, 44]); k.t(cs[i], x + 4.5, 32, 4, 'left');
        const T = k.n(x, 60, { gl: i < 4 ? 'b' + (3 - i) : '' }); k.w([[x, 44], T.d]); k.w([T.s, [x, 76]]); k.dot([x, 76]);
      });
      k.w([[24, 76], [104, 76]]); k.t('VIN / VREF / GND', 64, 84, 4.5);
      k.amp(140, 25.4, 12); k.t('VCM', 126.5, 30.8, 4.5, 'right'); k.t('→ SAR logic', 152, 38, 4.5, 'right');
    } },

  // PLL charge pump and loop filter: switched current sources set the VCO control voltage
  pll: { w: 130, h: 125, ports: { o: [130, 60, 'r'] },
    draw(k) {
      const M1 = k.p(40, 20, { fy: true, gl: 'Vbp' }), M2 = k.p(40, 44, { fy: true, gl: '~UP' });
      const M3 = k.n(40, 76, { gl: 'DN' }), M4 = k.n(40, 100, { gl: 'Vbn' });
      k.vdd(M1.s); k.gnd(M4.s);
      k.w([M1.d, M2.s]); k.w([M2.d, M3.d]); k.w([M3.s, M4.d]); k.dot([40, 60]);
      k.w([[40, 60], [130, 60]]);
      k.res([75, 60], [75, 84], { l: 'R', lx: 6, ly: 0 }); k.cap([75, 84], [75, 104], { l: 'C1', lx: 7, ly: 0 }); k.gnd([75, 104]); k.dot([75, 60]);
      k.cap([104, 60], [104, 86], { l: 'C2', lx: 7, ly: 0 }); k.gnd([104, 86]); k.dot([104, 60]);
      k.t('VCTRL → VCO', 127, 55, 4.5, 'right');
    } },

  // USB full-speed pads: CMOS drivers for D+ and D−, and the D+ pull-up that DETACH switches off
  usb: { w: 150, h: 138, ports: { dp: [150, 40, 'r'], dm: [150, 104, 'r'] },
    draw(k) {
      const I1 = k.inv(60, 40), I2 = k.inv(60, 104);
      k.t('TX+', I1.i[0] - 1.5, 40, 4.5, 'right'); k.t('TX−', I2.i[0] - 1.5, 104, 4.5, 'right');
      k.w([I1.o, [150, 40]]); k.w([I2.o, [150, 104]]);
      const P = k.p(125, 14, { fy: true, gl: 'DETACH' }); k.vdd(P.s, '3.3 V');
      k.res(P.d, [125, 40], { sz: 4 }); k.dot([125, 40]);
      k.t('D+', 146, 35, 5, 'right', COL.txt); k.t('D−', 146, 99, 5, 'right', COL.txt);
    } },
};

// ------------------------------------------------------------------ block = box + title + cell
const titleSize = r => Math.max(4, Math.min(r.h * 0.1, r.w * 0.075, 10));
export function cellLayout(name, r, o = {}) {
  const c = CELLS[name];
  if (!c) throw new Error('no cell ' + name);
  const th = r.l ? titleSize(r) * 1.3 : 0, pad = Math.min(r.w, r.h) * 0.04 + 1;
  const iw = r.w - 2 * pad, ih = r.h - th - 2 * pad, sc = Math.min(iw / c.w, ih / c.h);
  const ox = r.x + (r.w - c.w * sc) / 2, oy = r.y + th + pad + (ih - c.h * sc) / 2;
  const ports = {};
  for (const [n, [pu, pv, side]] of Object.entries(c.ports ?? {})) {
    const u = ox + (o.mirror ? c.w - pu : pu) * sc, v = oy + pv * sc;
    const sd = o.mirror ? ({ l: 'r', r: 'l' }[side] ?? side) : side;
    ports[n] = { at: [u, v], edge: sd === 'l' ? [r.x, v] : sd === 'r' ? [r.x + r.w, v] : sd === 't' ? [u, r.y] : [u, r.y + r.h] };
  }
  return { c, sc, ox, oy, th, ports };
}

// r: {x, y, w, h, l (title), fill, dash}; o: cell options, o.ckt names the cell
export function drawBlock(x, r, o, ui) {
  x.fillStyle = r.fill ?? COL.box; x.fillRect(r.x, r.y, r.w, r.h);
  x.strokeStyle = COL.boxLine; x.lineWidth = 1.6 * ui; if (r.dash) x.setLineDash([10, 7]);
  x.strokeRect(r.x, r.y, r.w, r.h); x.setLineDash([]);
  const L = cellLayout(o.ckt, r, o);
  if (r.l) {
    let fs = titleSize(r);
    x.font = `600 ${fs}px system-ui, sans-serif`;
    const w = x.measureText(r.l).width, max = r.w * 0.94;
    if (w > max) { fs *= max / w; x.font = `600 ${fs}px system-ui, sans-serif`; }
    x.fillStyle = COL.txt; x.textAlign = 'center'; x.textBaseline = 'middle';
    x.fillText(r.l, r.x + r.w / 2, r.y + Math.min(r.w, r.h) * 0.04 + 1 + L.th / 2);
  }
  x.save(); x.translate(o.mirror ? L.ox + L.c.w * L.sc : L.ox, L.oy); x.scale(o.mirror ? -L.sc : L.sc, L.sc);
  x.lineCap = 'round'; x.lineJoin = 'round';
  L.c.draw(kit(x, !!o.mirror), o);
  x.restore();
  x.strokeStyle = COL.wire; x.lineWidth = 1.1 * L.sc;
  for (const [n, pt] of Object.entries(L.ports)) {
    if (o.ports && !o.ports.includes(n)) continue;
    x.beginPath(); x.moveTo(...pt.at); x.lineTo(...pt.edge); x.stroke();
  }
  return L;
}
