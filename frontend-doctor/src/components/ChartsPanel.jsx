import { useMemo, useState } from 'react'
import {
  ResponsiveContainer, LineChart, Line,
  ScatterChart, Scatter,
  XAxis, YAxis, CartesianGrid, Tooltip, Legend, Cell,
} from 'recharts'
import Scatter3D from './Scatter3D.jsx'

const AXIS_TICK = { fill: '#8b97a6', fontSize: 11 }
const AXIS_LINE = { stroke: '#1e2a3a' }
const GRID_STROKE = '#1e2a3a'
const TOOLTIP_STYLE = {
  background: '#121822',
  border: '1px solid #2a3a50',
  borderRadius: 10,
  color: '#e6edf3',
  fontSize: 12,
}

// 根據症狀數量對應顏色強度
function severityColor(n) {
  if (n >= 5) return '#ff3d6a'
  if (n >= 3) return '#ff6b81'
  if (n >= 2) return '#ffb86b'
  return '#6ea8ff'
}

export default function ChartsPanel({ emotionTrend, medStats, symptoms, alerts, notes, medChanges }) {
  const [nowRef] = useState(() => Date.now())
  // 1. 折線圖：情緒 × 服藥率
  const lineData = useMemo(() => {
    const byDay = new Map()
    for (const e of emotionTrend ?? []) {
      if (!e.date || e.score == null) continue
      const cur = byDay.get(e.date) ?? { sum: 0, n: 0 }
      cur.sum += e.score * 20
      cur.n += 1
      byDay.set(e.date, cur)
    }
    const emotionByDay = new Map()
    for (const [d, v] of byDay) emotionByDay.set(d, Math.round(v.sum / v.n))
    const adherenceByDay = new Map()
    for (const a of medStats?.adherence_trend ?? []) adherenceByDay.set(a.date, a.rate)
    const allDays = new Set([...emotionByDay.keys(), ...adherenceByDay.keys()])
    return [...allDays].sort().map((d) => {
      const md = new Date(d)
      return {
        date: `${md.getMonth() + 1}/${md.getDate()}`,
        rawDate: d,
        emotion: emotionByDay.get(d) ?? null,
        adherence: adherenceByDay.get(d) ?? null,
      }
    })
  }, [emotionTrend, medStats])

  // 2. 散布圖：症狀 — x=日期序號 y=症狀數
  const symptomScatter = useMemo(() => {
    return (symptoms ?? []).map((s) => {
      const arr = Array.isArray(s.symptoms) ? s.symptoms : []
      const t = new Date(s.created_at).getTime()
      return {
        ts: t,
        date: new Date(s.created_at).toLocaleDateString('zh-TW'),
        count: arr.length,
        symptoms: arr.join('、'),
      }
    }).sort((a, b) => a.ts - b.ts)
  }, [symptoms])

  // 3. 閃點圖：事件密度（heatmap by category × week）
  const heatData = useMemo(() => {
    const types = ['情緒', '症狀', '備註', '警示', '調藥']
    const weeks = []
    for (let w = 11; w >= 0; w--) {
      const start = nowRef - (w + 1) * 7 * 86400_000
      const end = nowRef - w * 86400_000 * 7
      const weekLabel = new Date(start).toLocaleDateString('zh-TW', { month: 'numeric', day: 'numeric' })
      const counts = { 情緒: 0, 症狀: 0, 備註: 0, 警示: 0, 調藥: 0 }
      ;(emotionTrend ?? []).forEach((e) => {
        const t = new Date(e.date).getTime()
        if (t >= start && t < end) counts['情緒'] += 1
      })
      ;(symptoms ?? []).forEach((s) => {
        const t = new Date(s.created_at).getTime()
        if (t >= start && t < end) counts['症狀'] += 1
      })
      ;(notes ?? []).forEach((n) => {
        const t = new Date(n.created_at).getTime()
        if (t >= start && t < end) counts['備註'] += 1
      })
      ;(alerts ?? []).forEach((a) => {
        const t = new Date(a.created_at).getTime()
        if (t >= start && t < end) counts['警示'] += 1
      })
      ;(medChanges ?? []).forEach((m) => {
        const t = new Date(m.effective_date ?? m.created_at).getTime()
        if (t >= start && t < end) counts['調藥'] += 1
      })
      weeks.push({ week: weekLabel, ...counts })
    }
    return { weeks, types }
  }, [emotionTrend, symptoms, notes, alerts, medChanges, nowRef])

  // 4. 二維散布：情緒 vs 服藥率（每天一點，相關性視覺化）
  const corrData = useMemo(() => {
    return lineData
      .filter((d) => d.emotion != null && d.adherence != null)
      .map((d) => ({ x: d.adherence, y: d.emotion, date: d.date }))
  }, [lineData])

  return (
    <div className="charts-grid">
      {/* 折線圖 */}
      <ChartCard title="折線圖 — 情緒 × 服藥順從率（30 天）"
        sub="兩條趨勢線疊圖；情緒換算 0-100（=患者每日 1-5 評分 × 20）">
        {lineData.length > 0 ? (
          <ResponsiveContainer width="100%" height={260}>
            <LineChart data={lineData} margin={{ top: 8, right: 16, left: -8, bottom: 0 }}>
              <CartesianGrid stroke={GRID_STROKE} strokeDasharray="3 3" vertical={false} />
              <XAxis dataKey="date" tick={AXIS_TICK} tickLine={false} axisLine={AXIS_LINE} />
              <YAxis domain={[0, 100]} tick={AXIS_TICK} tickLine={false} axisLine={AXIS_LINE} />
              <Tooltip contentStyle={TOOLTIP_STYLE} />
              <Legend wrapperStyle={{ fontSize: 12, color: '#8b97a6' }} />
              <Line type="monotone" dataKey="emotion" name="情緒分數" stroke="#6ea8ff" strokeWidth={2} dot={{ r: 2.5 }} />
              <Line type="monotone" dataKey="adherence" name="服藥順從率 %" stroke="#3ddc97" strokeWidth={2} dot={{ r: 2.5 }} />
            </LineChart>
          </ResponsiveContainer>
        ) : <div className="placeholder">尚無資料</div>}
      </ChartCard>

      {/* 散布圖 */}
      <ChartCard title="散布圖 — 症狀分布"
        sub="每點為一次症狀分析；y 軸＝該次自述症狀數，色階表示嚴重度">
        {symptomScatter.length > 0 ? (
          <ResponsiveContainer width="100%" height={260}>
            <ScatterChart margin={{ top: 8, right: 16, left: -8, bottom: 0 }}>
              <CartesianGrid stroke={GRID_STROKE} strokeDasharray="3 3" />
              <XAxis dataKey="date" tick={AXIS_TICK} tickLine={false} axisLine={AXIS_LINE} />
              <YAxis dataKey="count" name="症狀數" tick={AXIS_TICK} tickLine={false} axisLine={AXIS_LINE} />
              <Tooltip cursor={{ strokeDasharray: '3 3' }} contentStyle={TOOLTIP_STYLE}
                formatter={(v, n, p) => n === '症狀數'
                  ? [`${v} 種`, n]
                  : [p.payload.symptoms, '症狀']} />
              <Scatter data={symptomScatter} fill="#ff6b81">
                {symptomScatter.map((d, i) => (
                  <Cell key={i} fill={severityColor(d.count)} />
                ))}
              </Scatter>
            </ScatterChart>
          </ResponsiveContainer>
        ) : <div className="placeholder">尚無症狀紀錄</div>}
      </ChartCard>

      {/* 閃點圖（密度 heatmap） */}
      <ChartCard title="閃點圖 — 事件密度（近 12 週）"
        sub="情緒 / 症狀 / 備註 / 警示 / 調藥 五類事件按週聚合，越亮代表該週越多事件">
        <Heatmap data={heatData} />
      </ChartCard>

      {/* 二維散布（情緒×順從率） */}
      <ChartCard title="二維散布 — 情緒 × 服藥順從率"
        sub="每天一點；右上角集中＝順從率高且情緒好">
        {corrData.length > 0 ? (
          <ResponsiveContainer width="100%" height={260}>
            <ScatterChart margin={{ top: 10, right: 16, left: -8, bottom: 0 }}>
              <CartesianGrid stroke={GRID_STROKE} strokeDasharray="3 3" />
              <XAxis type="number" dataKey="x" name="服藥順從率" unit="%" domain={[0, 100]}
                tick={AXIS_TICK} tickLine={false} axisLine={AXIS_LINE} />
              <YAxis type="number" dataKey="y" name="情緒分數" domain={[0, 100]}
                tick={AXIS_TICK} tickLine={false} axisLine={AXIS_LINE} />
              <Tooltip cursor={{ strokeDasharray: '3 3' }} contentStyle={TOOLTIP_STYLE} />
              <Scatter data={corrData} fill="#9a7bff" />
            </ScatterChart>
          </ResponsiveContainer>
        ) : <div className="placeholder">需要同時有情緒與服藥紀錄</div>}
      </ChartCard>

      {/* 真 3D 散布圖（plotly via CDN，可旋轉） */}
      <ChartCard title="3D 散布圖 — 日期 × 情緒 × 服藥率"
        sub="點顏色與大小＝當日症狀數；可滑鼠拖曳旋轉、滾輪縮放。">
        <Scatter3D
          emotionTrend={emotionTrend}
          medStats={medStats}
          symptoms={symptoms}
        />
      </ChartCard>
    </div>
  )
}

function ChartCard({ title, sub, children }) {
  return (
    <div className="card chart-card">
      <div className="chart-header">
        <div>
          <h3 className="chart-title">{title}</h3>
          {sub && <p className="chart-sub">{sub}</p>}
        </div>
      </div>
      {children}
    </div>
  )
}

// ─── 小型熱點圖（純 div，不靠 recharts）────────────────────────
function Heatmap({ data }) {
  const { weeks, types } = data
  // 每類型內 normalize 0..1
  const max = {}
  for (const t of types) max[t] = Math.max(1, ...weeks.map((w) => w[t] || 0))
  return (
    <div className="heatmap">
      <div className="heatmap-header">
        <span />
        {weeks.map((w, i) => (
          <span key={i} className="heatmap-col-label">{w.week}</span>
        ))}
      </div>
      {types.map((t) => (
        <div key={t} className="heatmap-row">
          <span className="heatmap-row-label">{t}</span>
          {weeks.map((w, i) => {
            const v = w[t] || 0
            const intensity = v / max[t]
            const bg = `rgba(110, 168, 255, ${0.08 + intensity * 0.85})`
            return (
              <span key={i} className="heatmap-cell" title={`${t} · ${w.week} · ${v} 件`}
                style={{ background: bg }}>
                {v > 0 && v}
              </span>
            )
          })}
        </div>
      ))}
    </div>
  )
}
