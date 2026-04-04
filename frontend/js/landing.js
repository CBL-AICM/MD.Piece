// ═══════════════════════════════════════════════════════════
// MD.Piece — Landing Cinematic Animation
// Phase 1: Puzzle pieces rain with scattered medical words
// Phase 2: Doctor + Patient hands enter, reaching to connect
// Phase 3: Hands connect → flash → pieces fly into heart
// Phase 4: Heart pulses with ECG line, tagline + button
// ═══════════════════════════════════════════════════════════

(function () {
  'use strict';

  const canvas = document.getElementById('landing-canvas');
  if (!canvas) return;
  const ctx = canvas.getContext('2d');
  let W, H, cx, cy;
  let running = true;
  const t0 = performance.now();

  // ── Timeline (seconds) ──
  const T = {
    rainEnd:    3.0,
    handsStart: 3.0,
    handsMeet:  5.5,
    flash:      5.8,
    handsGone:  6.8,
    heartStart: 6.0,
    heartDone:  8.2,
    heartbeat:  8.5,
    textShow:   9.0,
    btnShow:    10.0,
  };

  // ── Palette ──
  const PIECE_COLORS = [
    '#7EB5FF','#B49AE8','#E8A0B9','#7ECFA5','#F0C97A',
    '#A8D0FF','#CDB8F0','#D08A8A','#55B88A','#D9A54A',
    '#5B9FE8','#9B80D4','#E87B5B','#7BC8E8','#B8A080',
  ];
  const HEART_FILLS = [
    'rgba(232,224,210,0.90)','rgba(222,215,202,0.90)',
    'rgba(240,232,218,0.90)','rgba(228,220,208,0.90)',
    'rgba(235,228,215,0.90)','rgba(218,212,200,0.90)',
  ];
  const WORDS = [
    '疾病','未知','迷茫','藥','健康',
    '症狀','希望','治療','陪伴','守護',
    '診斷','康復','疼痛','勇氣','信任',
  ];

  // ── State ──
  let rainPcs = [];
  let heartCells = [];
  let flashAlpha = 0;
  let hbProg = 0;
  let textShown = false, btnShown = false;

  // ── Util ──
  const clamp = (v,a,b) => Math.max(a, Math.min(b, v));
  const lerp  = (a,b,t) => a + (b - a) * t;
  const easeO = t => 1 - Math.pow(1 - t, 3);
  const easeIO = t => t < .5 ? 4*t*t*t : 1 - Math.pow(-2*t+2, 3) / 2;

  function isInHeart(px, py, hcx, hcy, s) {
    const x = (px - hcx) / s;
    const y = -(py - hcy) / (s * 0.85) + 0.35;
    const x2 = x*x, y2 = y*y;
    return Math.pow(x2 + y2 - 1, 3) - x2 * y2 * y <= 0;
  }

  // ── Draw a jigsaw piece ──
  function drawPiece(x, y, sz, ang, col, alpha, word) {
    ctx.save();
    ctx.globalAlpha = clamp(alpha, 0, 1);
    ctx.translate(x, y);
    ctx.rotate(ang);
    const s = sz / 2, tab = s * 0.3;

    ctx.beginPath();
    ctx.moveTo(-s, -s);
    ctx.lineTo(-s*.15, -s);
    ctx.bezierCurveTo(-s*.15, -s-tab, s*.15, -s-tab, s*.15, -s);
    ctx.lineTo(s, -s);
    ctx.lineTo(s, -s*.15);
    ctx.bezierCurveTo(s+tab, -s*.15, s+tab, s*.15, s, s*.15);
    ctx.lineTo(s, s);
    ctx.lineTo(-s, s);
    ctx.lineTo(-s, s*.15);
    ctx.bezierCurveTo(-s-tab*.6, s*.15, -s-tab*.6, -s*.15, -s, -s*.15);
    ctx.closePath();

    ctx.fillStyle = col;
    ctx.fill();
    ctx.strokeStyle = 'rgba(255,255,255,0.45)';
    ctx.lineWidth = 1.2;
    ctx.stroke();

    if (word) {
      ctx.fillStyle = 'rgba(255,255,255,0.92)';
      ctx.font = `bold ${sz * 0.26}px "Noto Sans TC", sans-serif`;
      ctx.textAlign = 'center';
      ctx.textBaseline = 'middle';
      ctx.shadowColor = 'rgba(0,0,0,0.35)';
      ctx.shadowBlur = 3;
      ctx.fillText(word, 0, 0);
      ctx.shadowBlur = 0;
    }
    ctx.restore();
  }

  // ── Draw heart grid cell ──
  function drawCell(c) {
    if (c.alpha <= 0) return;
    ctx.save();
    ctx.globalAlpha = clamp(c.alpha, 0, 1);
    ctx.translate(c.x, c.y);
    const s = c.size / 2, tab = s * 0.22;

    ctx.beginPath();
    ctx.moveTo(-s, -s);
    if (c.tt) { ctx.lineTo(-s*.1,-s); ctx.bezierCurveTo(-s*.1,-s-tab, s*.1,-s-tab, s*.1,-s); }
    ctx.lineTo(s, -s);
    if (c.tr) { ctx.lineTo(s,-s*.1); ctx.bezierCurveTo(s+tab,-s*.1, s+tab,s*.1, s,s*.1); }
    ctx.lineTo(s, s);
    if (c.tb) { ctx.lineTo(s*.1,s); ctx.bezierCurveTo(s*.1,s+tab, -s*.1,s+tab, -s*.1,s); }
    ctx.lineTo(-s, s);
    if (c.tl) { ctx.lineTo(-s,s*.1); ctx.bezierCurveTo(-s-tab,s*.1, -s-tab,-s*.1, -s,-s*.1); }
    ctx.closePath();

    ctx.fillStyle = c.color;
    ctx.fill();
    ctx.strokeStyle = 'rgba(175,165,148,0.35)';
    ctx.lineWidth = 0.8;
    ctx.stroke();
    ctx.restore();
  }

  // ── Draw a hand (doctor or patient) ──
  function drawHand(isDoc, progress, fadeAlpha) {
    if (progress <= 0 || fadeAlpha <= 0) return;
    const ep = easeO(clamp(progress, 0, 1));
    const dir = isDoc ? -1 : 1;

    // Animate from bottom-corner toward center
    const sx = cx + dir * (W * 0.55 + 80);
    const sy = H + 180;
    const ex = cx + dir * 50;
    const ey = cy + 30;

    const hx = lerp(sx, ex, ep);
    const hy = lerp(sy, ey, ep);
    // Arm rotation: tilted when entering, straightens toward center
    const baseAng = isDoc ? (Math.PI * 0.65) : (-Math.PI * 0.65);
    const meetAng = isDoc ? (Math.PI * 0.5) : (-Math.PI * 0.5);
    const ang = lerp(baseAng, meetAng, ep);

    ctx.save();
    ctx.globalAlpha = clamp(fadeAlpha, 0, 1);
    ctx.translate(hx, hy);
    ctx.rotate(ang);

    // ── Forearm (long shape going "up" in local coords = toward corner) ──
    const aw = 48, ah = 240;
    ctx.fillStyle = 'rgba(242,237,230,0.93)';
    ctx.strokeStyle = 'rgba(50,55,70,0.28)';
    ctx.lineWidth = 2;
    ctx.beginPath();
    ctx.moveTo(-aw/2, 0);
    ctx.lineTo(-aw/2, ah);
    ctx.quadraticCurveTo(-aw/2, ah+15, 0, ah+15);
    ctx.quadraticCurveTo(aw/2, ah+15, aw/2, ah);
    ctx.lineTo(aw/2, 0);
    ctx.closePath();
    ctx.fill();
    ctx.stroke();

    // Sleeve cuff
    ctx.strokeStyle = 'rgba(50,55,70,0.2)';
    ctx.lineWidth = 1.5;
    ctx.beginPath();
    ctx.moveTo(-aw/2-2, 12); ctx.lineTo(aw/2+2, 12);
    ctx.moveTo(-aw/2-2, 18); ctx.lineTo(aw/2+2, 18);
    ctx.stroke();

    // ── Hand (palm + fingers, going "down" = toward center) ──
    ctx.fillStyle = 'rgba(235,226,215,0.92)';
    ctx.strokeStyle = 'rgba(50,55,70,0.25)';
    ctx.lineWidth = 2;

    // Palm
    ctx.beginPath();
    ctx.moveTo(-aw/2 - 4, 0);
    ctx.lineTo(-aw/2 - 4, -42);
    // 4 finger bumps
    const fw = (aw + 8) / 4;
    for (let i = 0; i < 4; i++) {
      const bx = -aw/2 - 4 + i * fw;
      ctx.quadraticCurveTo(bx + fw*0.5, -56, bx + fw, -42);
    }
    ctx.lineTo(aw/2 + 4, 0);
    ctx.closePath();
    ctx.fill();
    ctx.stroke();

    // Thumb (side of palm)
    const thumbSide = isDoc ? 1 : -1;
    ctx.beginPath();
    ctx.ellipse(thumbSide * (aw/2 + 14), -8, 10, 22, thumbSide * 0.25, 0, Math.PI * 2);
    ctx.fill();
    ctx.stroke();

    // ── Medical identifier ──
    if (isDoc) {
      // Blue cross on sleeve
      ctx.strokeStyle = 'rgba(91,159,232,0.75)';
      ctx.lineWidth = 3.5;
      ctx.lineCap = 'round';
      ctx.beginPath();
      ctx.moveTo(0, 70); ctx.lineTo(0, 92);
      ctx.moveTo(-11, 81); ctx.lineTo(11, 81);
      ctx.stroke();
    } else {
      // Pink wristband
      ctx.fillStyle = 'rgba(208,138,138,0.45)';
      ctx.beginPath();
      ctx.moveTo(-aw/2-2, 22); ctx.lineTo(aw/2+2, 22);
      ctx.lineTo(aw/2+2, 34); ctx.lineTo(-aw/2-2, 34);
      ctx.closePath();
      ctx.fill();
      ctx.strokeStyle = 'rgba(208,138,138,0.65)';
      ctx.lineWidth = 1;
      ctx.stroke();
    }

    // ── Puzzle piece held in fingers ──
    const pc = isDoc ? 'rgba(91,159,232,0.6)' : 'rgba(208,138,138,0.55)';
    drawPiece(0, -62, 30, 0, pc, 1, null);

    ctx.restore();
  }

  // ── Heart outline (parametric) ──
  function drawHeartOutline(alpha) {
    if (alpha <= 0) return;
    const s = getHeartScale();
    const hcy = getHeartCY();
    ctx.save();
    ctx.globalAlpha = alpha;
    ctx.strokeStyle = 'rgba(55,60,75,0.25)';
    ctx.lineWidth = 2.5;
    ctx.beginPath();
    for (let t = 0; t <= Math.PI * 2 + 0.1; t += 0.02) {
      const px = cx + 16 * Math.pow(Math.sin(t), 3) * s / 16;
      const py = hcy - (13*Math.cos(t) - 5*Math.cos(2*t) - 2*Math.cos(3*t) - Math.cos(4*t)) * s / 16;
      if (t === 0) ctx.moveTo(px, py); else ctx.lineTo(px, py);
    }
    ctx.closePath();
    ctx.stroke();
    ctx.restore();
  }

  // ── ECG heartbeat line ──
  function drawECG(progress) {
    if (progress <= 0) return;
    const s = getHeartScale();
    const hcy = getHeartCY();
    const lineW = s * 1.6;
    const startX = cx - lineW / 2;
    const baseY = hcy + s * 0.05;

    ctx.save();
    ctx.strokeStyle = 'rgba(91,159,232,0.7)';
    ctx.lineWidth = 2.5;
    ctx.lineCap = 'round';
    ctx.lineJoin = 'round';
    ctx.beginPath();

    const steps = Math.floor(progress * 200);
    for (let i = 0; i <= steps; i++) {
      const n = i / 200;
      const px = startX + n * lineW;
      let dy = 0;
      if      (n > 0.12 && n < 0.20) dy = -7 * Math.sin((n-0.12)/0.08*Math.PI);
      else if (n > 0.28 && n < 0.32) dy = 10;
      else if (n > 0.32 && n < 0.38) dy = -38 * Math.sin((n-0.32)/0.06*Math.PI);
      else if (n > 0.38 && n < 0.43) dy = 12 * Math.sin((n-0.38)/0.05*Math.PI);
      else if (n > 0.55 && n < 0.66) dy = -10 * Math.sin((n-0.55)/0.11*Math.PI);
      if (i === 0) ctx.moveTo(px, baseY + dy); else ctx.lineTo(px, baseY + dy);
    }
    ctx.stroke();
    ctx.restore();
  }

  // ── Flash ──
  function drawFlash() {
    if (flashAlpha <= 0) return;
    ctx.save();
    ctx.globalAlpha = flashAlpha;
    const g = ctx.createRadialGradient(cx, cy, 0, cx, cy, Math.max(W,H)*0.4);
    g.addColorStop(0, 'rgba(255,255,255,0.9)');
    g.addColorStop(0.4, 'rgba(200,220,255,0.3)');
    g.addColorStop(1, 'transparent');
    ctx.fillStyle = g;
    ctx.fillRect(0, 0, W, H);
    ctx.restore();
  }

  // ── Helpers for heart geometry ──
  function getHeartScale() { return Math.min(W, H) * 0.105; }
  function getHeartCY() { return cy - getHeartScale() * 0.3; }

  // ── Init ──
  function resize() {
    W = canvas.width = window.innerWidth;
    H = canvas.height = window.innerHeight;
    cx = W / 2;
    cy = H / 2 - 20;
  }

  function createRain() {
    rainPcs = [];
    for (let i = 0; i < WORDS.length; i++) {
      rainPcs.push({
        word: WORDS[i],
        color: PIECE_COLORS[i],
        size: 40 + Math.random() * 18,
        x: W * 0.08 + Math.random() * W * 0.84,
        y: -50 - Math.random() * 400,
        vx: (Math.random() - 0.5) * 1.2,
        vy: 2 + Math.random() * 3,
        angle: Math.random() * Math.PI * 2,
        va: (Math.random() - 0.5) * 0.03,
        sx: W * 0.1 + Math.random() * W * 0.8,
        sy: H * 0.15 + Math.random() * H * 0.55,
        hx: cx, hy: cy,
        settled: false,
        alpha: 1,
      });
    }
  }

  function createHeartGrid() {
    heartCells = [];
    const s = getHeartScale();
    const hcy = getHeartCY();
    const ps = 21;

    for (let y = hcy - s * 1.25; y < hcy + s * 0.95; y += ps) {
      for (let x = cx - s * 1.35; x < cx + s * 1.35; x += ps) {
        if (isInHeart(x, y, cx, hcy, s)) {
          heartCells.push({
            x, y, size: ps,
            color: HEART_FILLS[Math.floor(Math.random() * HEART_FILLS.length)],
            alpha: 0,
            tt: Math.random() > 0.5, tr: Math.random() > 0.5,
            tb: Math.random() > 0.5, tl: Math.random() > 0.5,
          });
        }
      }
    }

    // Assign heart targets to rain pieces (spread evenly)
    const step = Math.max(1, Math.floor(heartCells.length / rainPcs.length));
    for (let i = 0; i < rainPcs.length; i++) {
      const ci = Math.min(i * step, heartCells.length - 1);
      rainPcs[i].hx = heartCells[ci].x;
      rainPcs[i].hy = heartCells[ci].y;
    }
  }

  // ── Main Loop ──
  function animate(now) {
    if (!running) return;
    const t = (now - t0) / 1000;
    ctx.clearRect(0, 0, W, H);

    // ── Phase 1: Rain + scatter ──
    const isPreHeart = t < T.heartStart;
    for (const p of rainPcs) {
      if (isPreHeart) {
        if (!p.settled) {
          p.vy += 0.025;
          p.x += p.vx;
          p.y += p.vy;
          p.angle += p.va;
          // Begin settling
          if (t > T.rainEnd * 0.6) {
            const st = clamp((t - T.rainEnd * 0.6) / (T.rainEnd * 0.4), 0, 1);
            p.x = lerp(p.x, p.sx, st * 0.06);
            p.y = lerp(p.y, p.sy, st * 0.06);
            p.vx *= 0.97; p.vy *= 0.97; p.va *= 0.97;
            if (st > 0.85) p.settled = true;
          }
        }
        drawPiece(p.x, p.y, p.size, p.angle, p.color, p.alpha, p.word);
      } else {
        // Fly to heart
        const hp = easeIO(clamp((t - T.heartStart) / (T.heartDone - T.heartStart - 0.5), 0, 1));
        const fx = lerp(p.sx, p.hx, hp);
        const fy = lerp(p.sy, p.hy, hp);
        const fa = lerp(p.angle, 0, hp);
        const fAlpha = 1 - hp * 0.85;
        const fSize = p.size * (1 - hp * 0.35);
        if (hp < 0.95) {
          drawPiece(fx, fy, fSize, fa, p.color, fAlpha, hp < 0.4 ? p.word : null);
        }
      }
    }

    // ── Phase 2: Hands ──
    if (t >= T.handsStart) {
      const prog = clamp((t - T.handsStart) / (T.handsMeet - T.handsStart), 0, 1);
      let fade = 1;
      if (t > T.flash) fade = 1 - clamp((t - T.flash) / (T.handsGone - T.flash), 0, 1);
      drawHand(true, prog, fade);
      drawHand(false, prog, fade);
    }

    // ── Flash ──
    if (t >= T.flash && t < T.flash + 0.8) {
      flashAlpha = 1 - (t - T.flash) / 0.8;
    } else {
      flashAlpha = 0;
    }
    drawFlash();

    // ── Phase 3: Heart formation ──
    if (t >= T.heartStart) {
      const hp = clamp((t - T.heartStart) / (T.heartDone - T.heartStart), 0, 1);
      const ehp = easeIO(hp);

      // Staggered fade-in of cells
      for (let i = 0; i < heartCells.length; i++) {
        const delay = (i / heartCells.length) * 0.55;
        heartCells[i].alpha = clamp((ehp - delay) / (1 - delay), 0, 1);
        drawCell(heartCells[i]);
      }

      // Heart outline
      if (hp > 0.6) {
        drawHeartOutline(clamp((hp - 0.6) / 0.4, 0, 0.7));
      }
    }

    // ── Phase 4: Heartbeat ECG ──
    if (t >= T.heartbeat) {
      hbProg = clamp((t - T.heartbeat) / 2.2, 0, 1);
      drawECG(hbProg);
    }

    // ── Phase 5: Show text/button ──
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

    requestAnimationFrame(animate);
  }

  // ── Start ──
  resize();
  window.addEventListener('resize', () => { resize(); createHeartGrid(); });
  createRain();
  createHeartGrid();
  requestAnimationFrame(animate);

  window.stopLandingAnim = () => { running = false; };
})();
