// ═══════════════════════════════════════════════════════════
// MD.Piece — Landing Cinematic Animation (v2)
// 1. Warm puzzle pieces rain + floating words scatter separately
// 2. Doctor hand (from below) + Patient hand (from above) meet
// 3. Flash → pieces fly into heart shape filled with jigsaws
// 4. Bold heart outline + ECG heartbeat + tagline + enter
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
    handsStart: 3.2,
    handsMeet:  5.5,
    flash:      5.8,
    handsGone:  6.8,
    heartStart: 6.2,
    heartDone:  8.8,
    ecgStart:   9.0,
    textShow:   10.0,
    btnShow:    11.0,
  };

  /* ── Warm beige palette (matching reference images) ── */
  const PIECE_COLORS = [
    '#E8DDD0','#DDD1C2','#F0E5D5','#D5CCBF','#E3D8C8',
    '#CFC5B5','#EBE1D2','#D9CFC1','#E5DBCC','#D2C8B5',
    '#DFD5C5','#E7DCD0',
  ];
  const HEART_COLORS = [
    '#EDE4D8','#E0D7CB','#F2EBE0','#D8D0C5',
    '#E8DFD2','#DBD2C5','#EFE8DC','#E3DAD0',
    '#D5CCC0','#EEEAD6','#E6DDD0','#DED5C8',
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
     DRAW: Jigsaw piece (proper tabs/indents, warm style)
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
    // Top edge
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
    // Right edge
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
    // Bottom edge
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
    // Left edge
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

    // Shadow
    ctx.shadowColor = 'rgba(0,0,0,0.08)';
    ctx.shadowBlur = 5;
    ctx.shadowOffsetY = 2;
    ctx.fillStyle = color;
    ctx.fill();
    ctx.shadowBlur = 0;
    ctx.shadowOffsetY = 0;

    // Border
    ctx.strokeStyle = 'rgba(175,165,148,0.45)';
    ctx.lineWidth = 1.2;
    ctx.stroke();
    ctx.restore();
  }

  /* ═══════════════════════════════════════════════════════════
     DRAW: Floating word (separate from pieces)
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
     DRAW: Hand — bold line-art with bezier curves
     ═══════════════════════════════════════════════════════════ */
  function traceHand(ctx) {
    ctx.beginPath();
    // Start lower-left of forearm
    ctx.moveTo(-18, 160);
    ctx.lineTo(-18, 15);
    // Left palm up to pinky
    ctx.bezierCurveTo(-20, 5, -22, -5, -22, -12);
    // Pinky
    ctx.bezierCurveTo(-22, -22, -21, -35, -18, -42);
    ctx.bezierCurveTo(-16, -46, -13, -45, -12, -41);
    ctx.bezierCurveTo(-10, -35, -10, -28, -10, -22);
    // Ring
    ctx.bezierCurveTo(-9, -32, -7, -45, -5, -51);
    ctx.bezierCurveTo(-3, -54, 0, -53, 1, -49);
    ctx.bezierCurveTo(2, -42, 2, -32, 2, -24);
    // Middle (tallest)
    ctx.bezierCurveTo(3, -36, 5, -52, 7, -61);
    ctx.bezierCurveTo(9, -65, 12, -64, 13, -60);
    ctx.bezierCurveTo(14, -52, 14, -38, 14, -26);
    // Index
    ctx.bezierCurveTo(15, -36, 17, -48, 19, -55);
    ctx.bezierCurveTo(21, -58, 24, -57, 25, -53);
    ctx.bezierCurveTo(26, -46, 26, -36, 25, -26);
    // Right palm down to thumb gap
    ctx.bezierCurveTo(25, -16, 24, -6, 22, 0);
    // Thumb (extends right, always same side so rotation mirrors correctly)
    ctx.bezierCurveTo(26, -4, 33, -12, 37, -9);
    ctx.bezierCurveTo(41, -6, 41, 3, 37, 7);
    ctx.bezierCurveTo(33, 11, 26, 12, 22, 10);
    // Right forearm
    ctx.lineTo(18, 15);
    ctx.lineTo(18, 160);
    ctx.closePath();
  }

  function drawHand(isDoctor, progress, fadeAlpha) {
    if (progress <= 0 || fadeAlpha <= 0) return;
    const ep = easeO(clamp(progress, 0, 1));
    const sc = Math.min(W, H) / 550;

    let startY, endY, xOffset, rotation;
    if (isDoctor) {
      startY = H + 200;
      endY   = cy + 62 * sc;
      xOffset = -18 * sc;
      rotation = 0;
    } else {
      startY = -200;
      endY   = cy - 62 * sc;
      xOffset = 18 * sc;
      rotation = Math.PI;
    }

    const hx = cx + xOffset;
    const hy = lerp(startY, endY, ep);

    ctx.save();
    ctx.globalAlpha = clamp(fadeAlpha, 0, 1);
    ctx.translate(hx, hy);
    ctx.rotate(rotation);
    ctx.scale(sc, sc);

    // Hand fill (warm gradient)
    traceHand(ctx);
    const grad = ctx.createLinearGradient(0, -65, 0, 50);
    grad.addColorStop(0, 'rgba(240, 228, 212, 0.96)');
    grad.addColorStop(1, 'rgba(225, 210, 192, 0.96)');
    ctx.fillStyle = grad;
    ctx.fill();

    // Hand outline (bold line-art)
    traceHand(ctx);
    ctx.strokeStyle = '#3A3F4B';
    ctx.lineWidth = 2.8;
    ctx.lineCap = 'round';
    ctx.lineJoin = 'round';
    ctx.stroke();

    // Palm lines (subtle detail)
    ctx.strokeStyle = 'rgba(58, 63, 75, 0.15)';
    ctx.lineWidth = 1.2;
    ctx.beginPath();
    ctx.moveTo(-14, -8);
    ctx.quadraticCurveTo(0, -13, 16, -8);
    ctx.stroke();
    ctx.beginPath();
    ctx.moveTo(-10, 0);
    ctx.quadraticCurveTo(2, -4, 14, 0);
    ctx.stroke();

    // Sleeve cuff lines
    ctx.strokeStyle = 'rgba(58, 63, 75, 0.25)';
    ctx.lineWidth = 1.8;
    ctx.beginPath();
    ctx.moveTo(-20, 16); ctx.lineTo(20, 16);
    ctx.stroke();
    ctx.beginPath();
    ctx.moveTo(-20, 22); ctx.lineTo(20, 22);
    ctx.stroke();

    if (isDoctor) {
      // Medical cross on sleeve
      ctx.strokeStyle = 'rgba(91, 159, 232, 0.75)';
      ctx.lineWidth = 3.5;
      ctx.lineCap = 'round';
      ctx.beginPath();
      ctx.moveTo(0, 50); ctx.lineTo(0, 72);
      ctx.moveTo(-11, 61); ctx.lineTo(11, 61);
      ctx.stroke();
    } else {
      // Patient wristband
      ctx.fillStyle = 'rgba(232, 165, 185, 0.4)';
      ctx.fillRect(-20, 26, 40, 10);
      ctx.strokeStyle = 'rgba(208, 138, 160, 0.6)';
      ctx.lineWidth = 1;
      ctx.strokeRect(-20, 26, 40, 10);
    }

    // Puzzle piece held at fingertips
    const pc = isDoctor ? 'rgba(142, 183, 215, 0.85)' : 'rgba(232, 190, 200, 0.85)';
    drawJigsaw(5, -70, 22, 0, pc, 1,
      { top: 1, right: 0, bottom: -1, left: 0 });

    ctx.restore();
  }

  /* ═══════════════════════════════════════════════════════════
     DRAW: Heart outline (bold, parametric)
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
    const hcy = getHeartCY();
    const lineW = s * 1.8;
    const startX = cx - lineW / 2;
    const baseY = hcy + s * 0.06;

    ctx.save();
    // Glow
    ctx.shadowColor = 'rgba(91, 159, 232, 0.4)';
    ctx.shadowBlur = 8;
    ctx.strokeStyle = 'rgba(91, 159, 232, 0.85)';
    ctx.lineWidth = 3;
    ctx.lineCap = 'round';
    ctx.lineJoin = 'round';
    ctx.beginPath();

    const steps = Math.floor(progress * 200);
    for (let i = 0; i <= steps; i++) {
      const n = i / 200;
      const px = startX + n * lineW;
      let dy = 0;
      if      (n > 0.10 && n < 0.18) dy = -8 * Math.sin((n - 0.10) / 0.08 * Math.PI);
      else if (n > 0.26 && n < 0.30) dy = 12;
      else if (n > 0.30 && n < 0.37) dy = -48 * Math.sin((n - 0.30) / 0.07 * Math.PI);
      else if (n > 0.37 && n < 0.42) dy = 16 * Math.sin((n - 0.37) / 0.05 * Math.PI);
      else if (n > 0.53 && n < 0.64) dy = -12 * Math.sin((n - 0.53) / 0.11 * Math.PI);
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

    for (let y = hcy - s * 1.25; y < hcy + s * 0.95; y += spacing) {
      for (let x = cx - s * 1.35; x < cx + s * 1.35; x += spacing) {
        if (isInHeart(x, y, cx, hcy, s)) {
          heartPieces.push({
            x, y, size: ps, alpha: 0,
            color: HEART_COLORS[Math.floor(Math.random() * HEART_COLORS.length)],
            tabs: {
              top:    (Math.random() > .5 ? 1 : -1),
              right:  (Math.random() > .5 ? 1 : -1),
              bottom: (Math.random() > .5 ? 1 : -1),
              left:   (Math.random() > .5 ? 1 : -1),
            },
          });
        }
      }
    }

    // Map falling pieces → heart targets
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

      /* ── Floating words (separate from pieces) ── */
      for (const w of floatingWords) {
        if (preHeart) {
          if (t >= T.wordsStart) w.alpha = Math.min(w.alpha + 0.008, 0.7);
          drawWord(w.text, w.x, w.y, w.alpha, w.bob + t * 1.5);
        } else {
          w.alpha = Math.max(w.alpha - 0.025, 0);
          if (w.alpha > 0) drawWord(w.text, w.x, w.y, w.alpha, w.bob + t * 1.5);
        }
      }

      /* ── Phase 2: Hands (doctor from below, patient from above) ── */
      if (t >= T.handsStart) {
        const prog = clamp((t - T.handsStart) / (T.handsMeet - T.handsStart), 0, 1);
        let fade = 1;
        if (t > T.flash) fade = 1 - clamp((t - T.flash) / (T.handsGone - T.flash), 0, 1);
        drawHand(true, prog, fade);
        drawHand(false, prog, fade);
      }

      /* ── Flash ── */
      if (t >= T.flash && t < T.flash + 0.8) {
        flashAlpha = 1 - (t - T.flash) / 0.8;
      } else {
        flashAlpha = 0;
      }
      drawFlash();

      /* ── Phase 3: Heart formation ── */
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

      /* ── Phase 4: ECG ── */
      if (t >= T.ecgStart) {
        ecgProg = clamp((t - T.ecgStart) / 2.0, 0, 1);
        drawECG(ecgProg);
      }

      /* ── Phase 5: Text + Button ── */
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
