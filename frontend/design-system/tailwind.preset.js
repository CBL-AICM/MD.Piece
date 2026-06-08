/**
 * MD.Piece — 海邊記憶書 / Seaside Memory Book · Tailwind preset (Art Direction v4)
 * ---------------------------------------------------------------------------
 * Single source of truth = frontend/css/seaside-tokens.css. This preset maps
 * those CSS variables onto Tailwind scales so utilities and the token file never
 * drift. Colours point at CSS vars where light/夜紙-dark/長者 must switch at
 * runtime with no rebuild; the five anchors are inlined for editor previews.
 *
 * Usage (React/Tailwind/shadcn future — the live app is still vanilla today):
 *   // tailwind.config.js
 *   module.exports = {
 *     darkMode: 'class',                       // .dark on <html>
 *     presets: [require('./frontend/design-system/tailwind.preset.js')],
 *     content: ['./src/**\/*.{ts,tsx,html}'],
 *   }
 * Re-skin shadcn by pointing its vars (--background/--foreground/--primary/--radius)
 * at the seaside tokens. Senior mode scales via the --scale CSS var (no util change).
 */
module.exports = {
  theme: {
    extend: {
      colors: {
        // —— the five anchors (inlined for previews) ——
        ocean:  { DEFAULT: '#2C3943', deep: '#2C3943', 2: '#3A4954',
                  breeze: '#9DABB4', 'breeze-d': '#6E828E', 'breeze-l': '#C3CED4' },
        stone:  '#77726F',
        coral:  { milk: '#E5D4CA', d: '#C99F8C', l: '#F1E5DD' },
        shell:  { DEFAULT: '#ECE6E3', warm: '#F5F1EE', raised: '#F7F4F2' },

        // —— semantic roles (CSS vars → runtime light/dark/senior) ——
        surface: { 0: 'var(--surface-0)', 1: 'var(--surface-1)', 2: 'var(--surface-2)',
                   sunk: 'var(--surface-sunk)' },
        content: { DEFAULT: 'var(--content)', muted: 'var(--content-muted)', subtle: 'var(--content-subtle)' },
        line:    { DEFAULT: 'var(--line)', soft: 'var(--line-soft)', ink: 'var(--line-ink)' },
        primary: { DEFAULT: 'var(--primary)', fg: 'var(--primary-fg)' },
        action:  { DEFAULT: 'var(--action)', deep: 'var(--action-deep)' },
        accent:  { DEFAULT: 'var(--accent)', soft: 'var(--accent-soft)' },

        // —— clinical severity (always colour + icon + text) ——
        status: { calm: 'var(--status-calm)', watch: 'var(--status-watch)',
                  elevated: 'var(--status-elevated)', urgent: 'var(--status-urgent)' },
        sev:    { self: 'var(--sev-self)', clinic: 'var(--sev-clinic)', regional: 'var(--sev-regional)',
                  medical: 'var(--sev-medical)', er: 'var(--sev-er)' },

        // —— health-event registry (timeline / journey) ——
        ev: { medication: 'var(--ev-medication)', symptom: 'var(--ev-symptom)', lab: 'var(--ev-lab)',
              appointment: 'var(--ev-appointment)', hospitalization: 'var(--ev-hospitalization)',
              emotion: 'var(--ev-emotion)', education: 'var(--ev-education)', milestone: 'var(--ev-milestone)' },

        // —— 8 journey chapters ——
        chapter: { spring: '#A8B89C', rain: '#8FA0AC', summer: '#C9A95E', seaside: '#9DABB4',
                   twilight: '#B08A86', star: '#6E7E8C', library: '#C99F8C', horizon: '#7E9A86' },
      },

      fontFamily: {
        display: ['Zen Old Mincho', 'Noto Serif TC', 'serif'],          // headlines
        serif:   ['Cormorant Garamond', 'Noto Serif TC', 'Georgia', 'serif'], // editorial / numerals
        cjk:     ['Noto Serif TC', 'serif'],                            // Chinese body
        body:    ['Inter', 'Noto Serif TC', 'system-ui', 'sans-serif'], // latin body / UI
      },
      fontSize: {
        xs: ['0.8125rem', '1.6'], sm: ['0.875rem', '1.6'], base: ['1rem', '1.7'],
        lg: ['1.1875rem', '1.7'], xl: ['1.4375rem', '1.4'], '2xl': ['1.75rem', '1.3'],
        '3xl': ['2.25rem', '1.28'], '4xl': ['3rem', '1.22'],
      },
      letterSpacing: { display: '0.04em', eyebrow: '0.22em' },

      borderRadius: { sm: '16px', md: '24px', lg: '32px', pill: '999px',
                      wobble: '28px 24px 30px 26px / 26px 30px 24px 28px' },

      boxShadow: {
        soft:   '0 8px 24px rgba(44,57,67,.08)',
        medium: '0 12px 32px rgba(44,57,67,.12)',
        float:  '0 18px 48px rgba(44,57,67,.16)',
        press:  '0 2px 6px rgba(44,57,67,.10)',
      },

      transitionTimingFunction: {
        settle: 'cubic-bezier(0.34,1.32,0.5,1)',   // gentle snap-into-place
        out:    'cubic-bezier(0.22,1,0.36,1)',
        page:   'cubic-bezier(0.45,0,0.15,1)',     // storybook page turn
      },
      transitionDuration: { fast: '180ms', base: '280ms', slow: '460ms', piece: '760ms' },

      keyframes: {
        'sea-collect': {  // puzzle piece floats, rotates, snaps home (600–900ms)
          '0%':   { transform: 'translateY(-18px) rotate(-8deg) scale(.9)', opacity: '0' },
          '55%':  { transform: 'translateY(2px) rotate(3deg) scale(1.04)', opacity: '1' },
          '100%': { transform: 'translateY(0) rotate(0) scale(1)', opacity: '1' },
        },
        'sea-restore': {  // watercolour ripple / soft glow on memory return
          '0%':   { boxShadow: '0 0 0 0 rgba(229,212,202,0)' },
          '40%':  { boxShadow: '0 0 28px 6px rgba(229,212,202,.55)' },
          '100%': { boxShadow: '0 8px 24px rgba(44,57,67,.08)' },
        },
        'sea-float':    { '0%,100%': { transform: 'translateY(0)' }, '50%': { transform: 'translateY(-10px)' } },
        'sea-pageturn': {
          '0%':   { transform: 'perspective(1400px) rotateY(-14deg)', opacity: '0', transformOrigin: 'left center' },
          '100%': { transform: 'perspective(1400px) rotateY(0)', opacity: '1', transformOrigin: 'left center' },
        },
      },
      animation: {
        collect: 'sea-collect 760ms cubic-bezier(0.34,1.32,0.5,1) both',
        restore: 'sea-restore 900ms cubic-bezier(0.22,1,0.36,1) both',
        float:   'sea-float 6s ease-in-out infinite',
        page:    'sea-pageturn 460ms cubic-bezier(0.45,0,0.15,1) both',
      },
    },
  },
};
