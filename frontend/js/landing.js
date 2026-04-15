// ═══════════════════════════════════════════════════════════
// MD.Piece — Landing Cinematic Animation (v3)
// 1. Warm puzzle pieces rain + floating words scatter
// 2. Flash → pieces fly into heart shape filled with jigsaws
// 3. Bold heart outline + ECG heartbeat + tagline + enter
// ═══════════════════════════════════════════════════════════

(function () {
  'use strict';

  const canvas = document.getElementById('landing-canvas');
  if (!canvas) return;
  const ctx = canvas.getContext('2d');
  let W, H, cx, cy;
  let running = true;
  const t0 = performance.now();

  /* ── Timeline (seconds) ── */
  const T = {
    rainEnd:    3.0,
    wordsStart: 0.8,
    flash:      3.8,
    heartStart: 4.2,
    heartDone:  6.8,
    ecgStart:   7.0,
    textShow:   8.0,
    btnShow:    9.0,
  };

  /* ── Winter dusk palette ── */
  const PIECE_COLORS = [
    '#D8D1CC','#CEC5C0','#C5BDC0','#B8B6BE','#B0B1BB',
    '#A7A9B4','#9FA5B3','#989FB0','#CFC4BE','#D4C7C0',
    '#C2BCC0','#ABB0BE',
  ];
  const HEART_COLORS = [
    '#DDD5CF','#D4CCC6','#CBC4C2','#C4C0C3',
    '#B9BAC1','#B0B4BE','#A9AFBB','#9EA7B8',
    '#CFC7C3','#D8D0CA','#C6C0C0','#B8BDC7',
  ];
  const WORDS = ['疾病','未知','迷茫','藥','健康','症狀','希望','治療','陪伴','守護'];

  /* ── State ── */
  let pieces = [];
  let floatingWords = [];
  let heartPieces = [];
  let flashAlpha = 0;
  let ecgProg = 0;
  let textShown = false, btnShown = false;

  /* ── Utils ── */
  const clamp = (v, a, b) => Math.max(a, Math.min(b, v));
  const lerp  = (a, b, t) => a + (b - a) * t;
  const easeO  = t => 1 - Math.pow(1 - t, 3);
  const easeIO = t => t < .5 ? 4*t*t*t : 1 - Math.pow(-2*t+2, 3) / 2;

  /* ── Heart containment ── */
  function isInHeart(px, py, hcx, hcy, s) {
    const x = (px - hcx) / s;
    const y = -(py - hcy) / (s * 0.85) + 0.35;
    return Math.pow(x*x + y*y - 1, 3) - x*x * y*y * y <= 0;
  }

  /* ═══════════════════════════════════════════════════════════
     DRAW: Jigsaw piece
     ═══════════════════════════════════════════════════════════ */
  function drawJigsaw(x, y, size, angle, color, alpha, tabs) {
    if (alpha <= 0) return;
    if (!tabs) tabs = { top: 1, right: -1, bottom: 1, left: -1 };
    ctx.save();
    ctx.globalAlpha = clamp(alpha, 0, 1);
    ctx.translate(x, y);
    ctx.rotate(angle);

    const s = size / 2;
    const t = size * 0.17;

    ctx.beginPath();
    ctx.moveTo(-s, -s);
    if (tabs.top) {
      ctx.lineTo(-s * 0.28, -s);
      ctx.bezierCurveTo(-s * 0.18, -s - tabs.top * t * 0.5,
                         -s * 0.12, -s - tabs.top * t,
                         0, -s - tabs.top * t);
      ctx.bezierCurveTo( s * 0.12, -s - tabs.top * t,
                          s * 0.18, -s - tabs.top * t * 0.5,
                          s * 0.28, -s);
    }
    ctx.lineTo(s, -s);
    if (tabs.right) {
      ctx.lineTo(s, -s * 0.28);
      ctx.bezierCurveTo(s + tabs.right * t * 0.5, -s * 0.18,
                         s + tabs.right * t, -s * 0.12,
                         s + tabs.right * t, 0);
      ctx.bezierCurveTo(s + tabs.right * t, s * 0.12,
                         s + tabs.right * t * 0.5, s * 0.18,
                         s, s * 0.28);
    }
    ctx.lineTo(s, s);
    if (tabs.bottom) {
      ctx.lineTo(s * 0.28, s);
      ctx.bezierCurveTo(s * 0.18, s + tabs.bottom * t * 0.5,
                         s * 0.12, s + tabs.bottom * t,
                         0, s + tabs.bottom * t);
      ctx.bezierCurveTo(-s * 0.12, s + tabs.bottom * t,
                         -s * 0.18, s + tabs.bottom * t * 0.5,
                         -s * 0.28, s);
    }
    ctx.lineTo(-s, s);
    if (tabs.left) {
      ctx.lineTo(-s, s * 0.28);
      ctx.bezierCurveTo(-s - tabs.left * t * 0.5, s * 0.18,
                         -s - tabs.left * t, s * 0.12,
                         -s - tabs.left * t, 0);
      ctx.bezierCurveTo(-s - tabs.left * t, -s * 0.12,
                         -s - tabs.left * t * 0.5, -s * 0.18,
                         -s, -s * 0.28);
    }
    ctx.closePath();

    ctx.shadowColor = 'rgba(0,0,0,0.08)';
    ctx.shadowBlur = 5;
    ctx.shadowOffsetY = 2;
    ctx.fillStyle = color;
    ctx.fill();
    ctx.shadowBlur = 0;
    ctx.shadowOffsetY = 0;

    ctx.strokeStyle = 'rgba(72,83,100,0.18)';
    ctx.lineWidth = 1;
    ctx.stroke();
    ctx.restore();
  }

  /* ═══════════════════════════════════════════════════════════
     DRAW: Floating word
     ═══════════════════════════════════════════════════════════ */
  function drawWord(word, x, y, alpha, bob) {
    if (alpha <= 0) return;
    ctx.save();
    ctx.globalAlpha = clamp(alpha, 0, 1);
    const fs = Math.min(W, H) * 0.03;
    ctx.font = `300 ${fs}px "Noto Sans TC", sans-serif`;
    ctx.textAlign = 'center';
    ctx.textBaseline = 'middle';
    ctx.fillStyle = 'rgba(100, 95, 85, 0.55)';
    ctx.fillText(word, x, y + Math.sin(bob) * 3);
    ctx.restore();
  }

  /* ═══════════════════════════════════════════════════════════
     DRAW: Heart outline
     ═══════════════════════════════════════════════════════════ */
  function getHeartScale() { return Math.min(W, H) * 0.17; }
  function getHeartCY() { return cy - getHeartScale() * 0.12; }

  function drawHeartOutline(alpha) {
    if (alpha <= 0) return;
    const s = getHeartScale();
    const hcy = getHeartCY();
    ctx.save();
    ctx.globalAlpha = clamp(alpha, 0, 1);
    ctx.strokeStyle = '#3A3F4B';
    ctx.lineWidth = 3.5;
    ctx.lineCap = 'round';
    ctx.lineJoin = 'round';
    ctx.beginPath();
    for (let a = 0; a <= Math.PI * 2 + 0.05; a += 0.02) {
      const px = cx + 16 * Math.pow(Math.sin(a), 3) * s / 16;
      const py = hcy - (13*Math.cos(a) - 5*Math.cos(2*a)
                 - 2*Math.cos(3*a) - Math.cos(4*a)) * s / 16;
      if (a === 0) ctx.moveTo(px, py); else ctx.lineTo(px, py);
    }
    ctx.closePath();
    ctx.stroke();
    ctx.restore();
  }

  /* ═══════════════════════════════════════════════════════════
     DRAW: ECG heartbeat line
     ═══════════════════════════════════════════════════════════ */
  function drawECG(progress) {
    if (progress <= 0) return;
    const s = getHeartScale();
    const lineW = Math.max(W * 0.88, s * 2.4);
    const startX = cx - lineW / 2;
    const baseY = H * 0.76;

    ctx.save();
    ctx.shadowColor = 'rgba(130, 137, 164, 0.12)';
    ctx.shadowBlur = 4;
    ctx.strokeStyle = 'rgba(72, 83, 100, 0.18)';
    ctx.lineWidth = 2;
    ctx.lineCap = 'round';
    ctx.lineJoin = 'round';
    ctx.beginPath();

    const steps = Math.floor(progress * 200);
    for (let i = 0; i <= steps; i++) {
      const n = i / 200;
      const px = startX + n * lineW;
      let dy = 0;
      if      (n > 0.10 && n < 0.18) dy = -4 * Math.sin((n - 0.10) / 0.08 * Math.PI);
      else if (n > 0.26 && n < 0.30) dy = 6;
      else if (n > 0.30 && n < 0.37) dy = -24 * Math.sin((n - 0.30) / 0.07 * Math.PI);
      else if (n > 0.37 && n < 0.42) dy = 8 * Math.sin((n - 0.37) / 0.05 * Math.PI);
      else if (n > 0.53 && n < 0.64) dy = -6 * Math.sin((n - 0.53) / 0.11 * Math.PI);
      if (i === 0) ctx.moveTo(px, baseY + dy); else ctx.lineTo(px, baseY + dy);
    }
    ctx.stroke();
    ctx.shadowBlur = 0;
    ctx.restore();
  }

  /* ═══════════════════════════════════════════════════════════
     DRAW: Flash
     ═══════════════════════════════════════════════════════════ */
  function drawFlash() {
    if (flashAlpha <= 0) return;
    ctx.save();
    ctx.globalAlpha = flashAlpha;
    const g = ctx.createRadialGradient(cx, cy, 0, cx, cy, Math.max(W, H) * 0.5);
    g.addColorStop(0, 'rgba(255,255,255,0.95)');
    g.addColorStop(0.3, 'rgba(220,230,255,0.4)');
    g.addColorStop(1, 'transparent');
    ctx.fillStyle = g;
    ctx.fillRect(0, 0, W, H);
    ctx.restore();
  }

  /* ═══════════════════════════════════════════════════════════
     INITIALIZATION
     ═══════════════════════════════════════════════════════════ */
  function resize() {
    W = canvas.width = window.innerWidth;
    H = canvas.height = window.innerHeight;
    cx = W / 2;
    cy = H / 2 - 20;
  }

  const TAB_CONFIGS = [
    { top: 1, right:-1, bottom: 1, left: 0 },
    { top:-1, right: 1, bottom: 0, left:-1 },
    { top: 0, right:-1, bottom:-1, left: 1 },
    { top: 1, right: 0, bottom:-1, left: 1 },
    { top:-1, right:-1, bottom: 1, left: 0 },
    { top: 0, right: 1, bottom: 1, left:-1 },
  ];

  function createPieces() {
    pieces = [];
    for (let i = 0; i < 12; i++) {
      pieces.push({
        color: PIECE_COLORS[i],
        size: 36 + Math.random() * 22,
        tabs: TAB_CONFIGS[i % TAB_CONFIGS.length],
        x: W * 0.1 + Math.random() * W * 0.8,
        y: -50 - Math.random() * 500,
        vx: (Math.random() - 0.5) * 1.5,
        vy: 2 + Math.random() * 3.5,
        angle: Math.random() * Math.PI * 2,
        va: (Math.random() - 0.5) * 0.04,
        sx: W * 0.08 + Math.random() * W * 0.84,
        sy: H * 0.15 + Math.random() * H * 0.55,
        hx: cx, hy: cy,
        settled: false,
        alpha: 1,
      });
    }
  }

  function createWords() {
    floatingWords = [];
    for (let i = 0; i < WORDS.length; i++) {
      floatingWords.push({
        text: WORDS[i],
        x: W * 0.12 + Math.random() * W * 0.76,
        y: H * 0.1 + Math.random() * H * 0.6,
        alpha: 0,
        bob: Math.random() * Math.PI * 2,
      });
    }
  }

  function createHeartPieces() {
    heartPieces = [];
    const s = getHeartScale();
    const hcy = getHeartCY();
    const ps = Math.max(32, s * 0.36);
    const spacing = ps * 0.88;

    // Extend bounds to fully cover the heart (bottom tip reaches ~hcy + 1.15s)
    const yStart = hcy - s * 1.3;
    const yEnd   = hcy + s * 1.25;
    const xStart = cx  - s * 1.6;
    const xEnd   = cx  + s * 1.6;

    // Track piece index by grid position so adjacent tabs can interlock
    const indexMap = new Map(); // "col,row" → index in heartPieces

    let row = 0;
    for (let y = yStart; y < yEnd; y += spacing, row++) {
      let col = 0;
      for (let x = xStart; x < xEnd; x += spacing, col++) {
        if (!isInHeart(x, y, cx, hcy, s)) continue;

        // Derive left/top tabs from neighbours so pieces interlock
        const leftIdx = indexMap.get(`${col - 1},${row}`);
        const topIdx  = indexMap.get(`${col},${row - 1}`);

        const rightTab  = Math.random() > 0.5 ? 1 : -1;
        const bottomTab = Math.random() > 0.5 ? 1 : -1;
        const leftTab   = leftIdx !== undefined
          ? -heartPieces[leftIdx].tabs.right
          : (Math.random() > 0.5 ? 1 : -1);
        const topTab    = topIdx !== undefined
          ? -heartPieces[topIdx].tabs.bottom
          : (Math.random() > 0.5 ? 1 : -1);

        indexMap.set(`${col},${row}`, heartPieces.length);
        heartPieces.push({
          x, y, size: ps, alpha: 0,
          color: HEART_COLORS[Math.floor(Math.random() * HEART_COLORS.length)],
          tabs: { top: topTab, right: rightTab, bottom: bottomTab, left: leftTab },
        });
      }
    }

    if (heartPieces.length > 0) {
      const step = Math.max(1, Math.floor(heartPieces.length / pieces.length));
      for (let i = 0; i < pieces.length; i++) {
        const idx = Math.min(i * step, heartPieces.length - 1);
        pieces[i].hx = heartPieces[idx].x;
        pieces[i].hy = heartPieces[idx].y;
      }
    }
  }

  /* ═══════════════════════════════════════════════════════════
     ANIMATION LOOP
     ═══════════════════════════════════════════════════════════ */
  function animate(now) {
    if (!running) return;
    const t = (now - t0) / 1000;
    ctx.clearRect(0, 0, W, H);

    try {
      const preHeart = t < T.heartStart;

      /* ── Phase 1: Puzzle pieces rain ── */
      for (const p of pieces) {
        if (preHeart) {
          if (!p.settled) {
            p.vy += 0.03;
            p.x += p.vx;
            p.y += p.vy;
            p.angle += p.va;
            if (t > T.rainEnd * 0.5) {
              const st = clamp((t - T.rainEnd * 0.5) / (T.rainEnd * 0.5), 0, 1);
              p.x = lerp(p.x, p.sx, st * 0.06);
              p.y = lerp(p.y, p.sy, st * 0.06);
              p.vx *= 0.97; p.vy *= 0.97; p.va *= 0.97;
              if (st > 0.9) p.settled = true;
            }
          }
          drawJigsaw(p.x, p.y, p.size, p.angle, p.color, p.alpha, p.tabs);
        } else {
          const hp = easeIO(clamp((t - T.heartStart) / (T.heartDone - T.heartStart - 0.5), 0, 1));
          const fx = lerp(p.sx, p.hx, hp);
          const fy = lerp(p.sy, p.hy, hp);
          const fa = lerp(p.angle, 0, hp);
          const fAlpha = 1 - hp * 0.9;
          const fSz = p.size * (1 - hp * 0.4);
          if (hp < 0.95) drawJigsaw(fx, fy, fSz, fa, p.color, fAlpha, p.tabs);
        }
      }

      /* ── Floating words ── */
      for (const w of floatingWords) {
        if (preHeart) {
          if (t >= T.wordsStart) w.alpha = Math.min(w.alpha + 0.008, 0.7);
          drawWord(w.text, w.x, w.y, w.alpha, w.bob + t * 1.5);
        } else {
          w.alpha = Math.max(w.alpha - 0.025, 0);
          if (w.alpha > 0) drawWord(w.text, w.x, w.y, w.alpha, w.bob + t * 1.5);
        }
      }

      /* ── Flash ── */
      if (t >= T.flash && t < T.flash + 0.8) {
        flashAlpha = 1 - (t - T.flash) / 0.8;
      } else {
        flashAlpha = 0;
      }
      drawFlash();

      /* ── Phase 2: Heart formation ── */
      if (t >= T.heartStart) {
        const hp = clamp((t - T.heartStart) / (T.heartDone - T.heartStart), 0, 1);
        const ehp = easeIO(hp);
        for (let i = 0; i < heartPieces.length; i++) {
          const delay = (i / heartPieces.length) * 0.5;
          heartPieces[i].alpha = clamp((ehp - delay) / (1 - delay), 0, 1);
          if (heartPieces[i].alpha > 0) {
            drawJigsaw(
              heartPieces[i].x, heartPieces[i].y,
              heartPieces[i].size, 0,
              heartPieces[i].color, heartPieces[i].alpha,
              heartPieces[i].tabs
            );
          }
        }
        if (hp > 0.65) drawHeartOutline(clamp((hp - 0.65) / 0.3, 0, 0.85));
      }

      /* ── Phase 3: ECG ── */
      if (t >= T.ecgStart) {
        ecgProg = clamp((t - T.ecgStart) / 2.0, 0, 1);
        drawECG(ecgProg);
      }

      /* ── Phase 4: Text + Button ── */
      if (t >= T.textShow && !textShown) {
        textShown = true;
        const el = document.getElementById('landing-text');
        if (el) el.classList.add('show');
      }
      if (t >= T.btnShow && !btnShown) {
        btnShown = true;
        const el = document.getElementById('landing-enter');
        if (el) el.classList.add('show');
      }
    } catch (err) {
      console.error('[landing] animation error:', err);
    }

    requestAnimationFrame(animate);
  }

  /* ── Start ── */
  resize();
  window.addEventListener('resize', () => { resize(); createHeartPieces(); });
  createPieces();
  createWords();
  createHeartPieces();
  requestAnimationFrame(animate);

  window.stopLandingAnim = () => { running = false; };
})();
