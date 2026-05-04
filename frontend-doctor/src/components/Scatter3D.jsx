import { useEffect, useMemo, useRef, useState } from 'react'

// 用 plotly.js (via CDN script tag) 做可旋轉的真 3D 散布圖
// 不放進 npm bundle，按需 lazy load 一次

const PLOTLY_URL = 'https://cdn.plot.ly/plotly-2.35.2.min.js'
let _plotlyPromise = null

function loadPlotly() {
  if (typeof window === 'undefined') return Promise.reject(new Error('SSR not supported'))
  if (window.Plotly) return Promise.resolve(window.Plotly)
  if (_plotlyPromise) return _plotlyPromise
  _plotlyPromise = new Promise((resolve, reject) => {
    const s = document.createElement('script')
    s.src = PLOTLY_URL
    s.async = true
    s.onload = () => window.Plotly ? resolve(window.Plotly) : reject(new Error('Plotly failed to attach'))
    s.onerror = () => reject(new Error('plotly CDN 載入失敗'))
    document.head.appendChild(s)
  })
  return _plotlyPromise
}

export default function Scatter3D({ emotionTrend, medStats, symptoms }) {
  const ref = useRef(null)
  const [err, setErr] = useState(null)
  const [ready, setReady] = useState(false)

  const points = useMemo(() => {
    // 把每天的 (情緒, 服藥率, 症狀數) 組成 3D 點
    const byDay = new Map()
    const get = (d) => {
      if (!byDay.has(d)) byDay.set(d, { date: d, emotion: null, adherence: null, symptoms: 0 })
      return byDay.get(d)
    }
    const emoMap = new Map()
    for (const e of emotionTrend ?? []) {
      if (!e.date || e.score == null) continue
      const cur = emoMap.get(e.date) ?? { sum: 0, n: 0 }
      cur.sum += e.score * 20
      cur.n += 1
      emoMap.set(e.date, cur)
    }
    for (const [d, v] of emoMap) get(d).emotion = Math.round(v.sum / v.n)
    for (const a of medStats?.adherence_trend ?? []) get(a.date).adherence = a.rate
    for (const s of symptoms ?? []) {
      const d = (s.created_at || '').slice(0, 10)
      if (!d) continue
      const arr = Array.isArray(s.symptoms) ? s.symptoms : []
      get(d).symptoms += arr.length
    }
    return [...byDay.values()].filter((d) => d.emotion != null && d.adherence != null)
  }, [emotionTrend, medStats, symptoms])

  useEffect(() => {
    if (!ref.current) return
    let cancelled = false
    loadPlotly().then((Plotly) => {
      if (cancelled || !ref.current) return
      const data = [{
        type: 'scatter3d',
        mode: 'markers',
        x: points.map((p) => p.date),
        y: points.map((p) => p.emotion),
        z: points.map((p) => p.adherence),
        text: points.map((p) =>
          `${p.date}<br>情緒 ${p.emotion}/100<br>服藥率 ${p.adherence}%<br>症狀 ${p.symptoms} 筆`
        ),
        hoverinfo: 'text',
        marker: {
          size: points.map((p) => Math.max(4, Math.min(14, 4 + p.symptoms * 2))),
          color: points.map((p) => p.symptoms),
          colorscale: [
            [0, '#6ea8ff'], [0.5, '#ffb86b'], [1, '#ff3d6a'],
          ],
          opacity: 0.85,
          line: { color: 'rgba(255,255,255,0.15)', width: 0.5 },
        },
      }]
      const layout = {
        autosize: true,
        height: 360,
        paper_bgcolor: 'rgba(0,0,0,0)',
        plot_bgcolor: 'rgba(0,0,0,0)',
        margin: { l: 0, r: 0, t: 0, b: 0 },
        font: { color: '#8b97a6', size: 11 },
        scene: {
          xaxis: { title: '日期', color: '#8b97a6', gridcolor: '#1e2a3a' },
          yaxis: { title: '情緒（0-100）', color: '#8b97a6', gridcolor: '#1e2a3a', range: [0, 100] },
          zaxis: { title: '服藥率 %', color: '#8b97a6', gridcolor: '#1e2a3a', range: [0, 100] },
          bgcolor: 'rgba(0,0,0,0)',
        },
        showlegend: false,
      }
      Plotly.newPlot(ref.current, data, layout, { displayModeBar: false, responsive: true })
      setReady(true)
    }).catch((e) => setErr(e.message))
    return () => {
      cancelled = true
      if (ref.current && window.Plotly) {
        try { window.Plotly.purge(ref.current) } catch { /* ignore */ }
      }
    }
  }, [points])

  if (err) return <div className="placeholder">3D 圖載入失敗：{err}</div>
  if (points.length === 0) return <div className="placeholder">尚無同時有情緒與服藥率的資料</div>
  return (
    <>
      <div ref={ref} style={{ width: '100%', height: 360 }} />
      {!ready && <p className="cell-dim" style={{ marginTop: 6, fontSize: 12 }}>載入 Plotly…</p>}
    </>
  )
}
