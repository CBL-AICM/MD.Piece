// ═══════════════════════════════════════════════════════════
// MD.Piece — Landing Animation (v4)
// Floating puzzle pieces drift through space, gently orbiting
// Clean fade-in of content after a brief delay
// ═══════════════════════════════════════════════════════════

(function () {
  'use strict';

  const canvas = document.getElementById('landing-canvas');
  if (!canvas) return;
  const ctx = canvas.getContext('2d');
  let W, H;
  let running = true;
  const t0 = performance.now();

  /* ── Color palette (space medical theme) ── */
  const COLORS = [
    'rgba(43,92,230,0.12)',   // accent blue
    'rgba(0,212,170,0.10)',   // teal
    'rgba(124,107,196,0.10)', // purple
    'rgba(0,47,167,0.08)',    // klein blue
    'rgba(232,220,200,0.06)', // cream
  ];

  /* ── Puzzle pieces floating in space ── */
  let pieces = [];
  const PIECE_COUNT = 18;

  /* ── Particle stars (tiny dots) ── */
  let particles = [];
  const PARTICLE_COUNT = 60;

  /* ── Draw a jigsaw piece ── */
  function drawJigsaw(x, y, size, angle, color, alpha) {
    if (alpha <= 0) return;
    ctx.save();
    ctx.globalAlpha = alpha;
    ctx.translate(x, y);
    ctx.rotate(angle);

    const s = size / 2;
    const t = size * 0.17;

    ctx.beginPath();
    // Top with tab
    ctx.moveTo(-s, -s);
    ctx.lineTo(-s * 0.28, -s);
    ctx.bezierCurveTo(-s * 0.18, -s - t * 0.5, -s * 0.12, -s - t, 0, -s - t);
    ctx.bezierCurveTo(s * 0.12, -s - t, s * 0.18, -s - t * 0.5, s * 0.28, -s);
    ctx.lineTo(s, -s);
    // Right with tab
    ctx.lineTo(s, -s * 0.28);
    ctx.bezierCurveTo(s + t * 0.5, -s * 0.18, s + t, -s * 0.12, s + t, 0);
    ctx.bezierCurveTo(s + t, s * 0.12, s + t * 0.5, s * 0.18, s, s * 0.28);
    ctx.lineTo(s, s);
    // Bottom with notch
    ctx.lineTo(s * 0.28, s);
    ctx.bezierCurveTo(s * 0.18, s - t * 0.5, s * 0.12, s - t, 0, s - t);
    ctx.bezierCurveTo(-s * 0.12, s - t, -s * 0.18, s - t * 0.5, -s * 0.28, s);
    ctx.lineTo(-s, s);
    // Left with notch
    ctx.lineTo(-s, s * 0.28);
    ctx.bezierCurveTo(-s - t * 0.5, s * 0.18, -s - t, s * 0.12, -s - t, 0);
    ctx.bezierCurveTo(-s - t, -s * 0.12, -s - t * 0.5, -s * 0.18, -s, -s * 0.28);
    ctx.closePath();

    ctx.fillStyle = color;
    ctx.fill();

    ctx.strokeStyle = 'rgba(255,255,255,0.08)';
    ctx.lineWidth = 1;
    ctx.stroke();

    ctx.restore();
  }

  /* ── Create floating pieces ── */
  function createPieces() {
    pieces = [];
    for (let i = 0; i < PIECE_COUNT; i++) {
      pieces.push({
        x: Math.random() * W,
        y: Math.random() * H,
        size: 30 + Math.random() * 50,
        angle: Math.random() * Math.PI * 2,
        va: (Math.random() - 0.5) * 0.003,
        vx: (Math.random() - 0.5) * 0.4,
        vy: (Math.random() - 0.5) * 0.3 - 0.1,
        color: COLORS[Math.floor(Math.random() * COLORS.length)],
        alpha: 0.3 + Math.random() * 0.5,
        phase: Math.random() * Math.PI * 2,
      });
    }
  }

  function createParticles() {
    particles = [];
    for (let i = 0; i < PARTICLE_COUNT; i++) {
      particles.push({
        x: Math.random() * W,
        y: Math.random() * H,
        r: Math.random() * 2 + 0.5,
        alpha: Math.random() * 0.4 + 0.1,
        speed: Math.random() * 0.003 + 0.001,
        phase: Math.random() * Math.PI * 2,
      });
    }
  }

  /* ── Resize ── */
  function resize() {
    W = canvas.width = window.innerWidth;
    H = canvas.height = window.innerHeight;
  }

  /* ── Timeline ── */
  const T_CONTENT = 2.0;  // seconds before content fades in
  const T_BTN = 3.0;      // seconds before button appears
  let contentShown = false;
  let btnShown = false;

  /* ── Animation loop ── */
  function animate(now) {
    if (!running) return;
    const t = (now - t0) / 1000;
    ctx.clearRect(0, 0, W, H);

    // Floating puzzle pieces
    for (const p of pieces) {
      p.x += p.vx + Math.sin(t * 0.5 + p.phase) * 0.15;
      p.y += p.vy + Math.cos(t * 0.3 + p.phase) * 0.1;
      p.angle += p.va;

      // Wrap around edges
      if (p.x < -80) p.x = W + 80;
      if (p.x > W + 80) p.x = -80;
      if (p.y < -80) p.y = H + 80;
      if (p.y > H + 80) p.y = -80;

      // Gentle breathing alpha
      const breathe = 0.85 + 0.15 * Math.sin(t * 0.8 + p.phase);
      drawJigsaw(p.x, p.y, p.size, p.angle, p.color, p.alpha * breathe);
    }

    // Tiny particles (like dust motes in space)
    for (const pt of particles) {
      const a = pt.alpha * (0.5 + 0.5 * Math.sin(t * pt.speed * 300 + pt.phase));
      ctx.beginPath();
      ctx.arc(pt.x, pt.y, pt.r, 0, Math.PI * 2);
      ctx.fillStyle = `rgba(200, 220, 255, ${a})`;
      ctx.fill();
    }

    // Show content after delay
    if (t >= T_CONTENT && !contentShown) {
      contentShown = true;
      const el = document.getElementById('landing-text');
      if (el) el.classList.add('show');
    }

    // Button is already visible in the split layout (no separate show needed)
    // but we keep it for the smooth entry
    if (t >= T_BTN && !btnShown) {
      btnShown = true;
    }

    requestAnimationFrame(animate);
  }

  /* ── Start ── */
  resize();
  window.addEventListener('resize', () => {
    resize();
    createPieces();
    createParticles();
  });
  createPieces();
  createParticles();
  requestAnimationFrame(animate);

  window.stopLandingAnim = () => { running = false; };
})();
