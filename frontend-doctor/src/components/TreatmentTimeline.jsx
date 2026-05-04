import { useMemo } from 'react'
import {
  ResponsiveContainer, ComposedChart, Line, Bar,
  XAxis, YAxis, CartesianGrid, Tooltip, Legend, ReferenceLine,
} from 'recharts'

const CHANGE_LABEL = {
  start: '新增', stop: '停藥', dose_up: '加量', dose_down: '減量',
  switch: '換藥', frequency: '頻次', other: '調整',
}
const CHANGE_COLOR = {
  start: '#3ddc97', stop: '#ff6b81', dose_up: '#ffb86b',
  dose_down: '#9a7bff', switch: '#6ea8ff', frequency: '#5a6572', other: '#5a6572',
}

export default function TreatmentTimeline({ symptoms, emotionTrend, medChanges, medStats }) {
  // 把症狀數量、情緒、服藥率都壓到日期序列上
  const series = useMemo(() => {
    const byDay = new Map()
    const get = (d) => {
      if (!byDay.has(d)) byDay.set(d, { date: d, symptomCount: 0, emotion: null, adherence: null })
      return byDay.get(d)
    }
    for (const s of symptoms ?? []) {
      const d = (s.created_at || '').slice(0, 10)
      if (!d) continue
      const arr = Array.isArray(s.symptoms) ? s.symptoms : []
      get(d).symptomCount += arr.length
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
    return [...byDay.values()].sort((a, b) => a.date.localeCompare(b.date)).map((d) => {
      const md = new Date(d.date)
      return { ...d, label: `${md.getMonth() + 1}/${md.getDate()}` }
    })
  }, [symptoms, emotionTrend, medStats])

  // 調藥事件
  const changes = useMemo(() => {
    return [...(medChanges ?? [])].sort((a, b) =>
      new Date(a.effective_date ?? a.created_at) - new Date(b.effective_date ?? b.created_at)
    )
  }, [medChanges])

  // 對每次調藥計算「前 7 天 vs 後 7 天」的症狀數 / 情緒平均
  const compares = useMemo(() => {
    return changes.map((c) => {
      const t = new Date(c.effective_date ?? c.created_at).getTime()
      if (Number.isNaN(t)) return null
      const before = window7(series, t, -7)
      const after = window7(series, t, 7)
      return { change: c, before, after }
    }).filter(Boolean)
  }, [changes, series])

  if (series.length === 0 && changes.length === 0) {
    return <div className="placeholder">尚無症狀／情緒／調藥資料</div>
  }

  // 為了在圖上畫垂直線，把 medChanges 的 effective_date 對到 series.label
  const dateToLabel = new Map(series.map((s) => [s.date, s.label]))
  const lineEvents = changes.map((c) => {
    const d = ((c.effective_date ?? c.created_at) || '').slice(0, 10)
    return { label: dateToLabel.get(d) || d.slice(5), c }
  })

  return (
    <>
      <div className="card">
        <h3 className="section-h">治療歷程整合圖</h3>
        <p className="cell-dim" style={{ marginTop: -6, fontSize: 12.5 }}>
          灰柱＝當日症狀筆數；藍線＝情緒分數；綠線＝服藥順從率；垂直虛線＝調藥事件。
        </p>
        <ResponsiveContainer width="100%" height={320}>
          <ComposedChart data={series} margin={{ top: 12, right: 16, left: -8, bottom: 0 }}>
            <CartesianGrid stroke="#1e2a3a" strokeDasharray="3 3" vertical={false} />
            <XAxis dataKey="label" tick={{ fill: '#8b97a6', fontSize: 11 }} tickLine={false} axisLine={{ stroke: '#1e2a3a' }} />
            <YAxis yAxisId="left" tick={{ fill: '#8b97a6', fontSize: 11 }} tickLine={false} axisLine={{ stroke: '#1e2a3a' }} />
            <YAxis yAxisId="right" orientation="right" domain={[0, 100]} tick={{ fill: '#8b97a6', fontSize: 11 }} tickLine={false} axisLine={{ stroke: '#1e2a3a' }} />
            <Tooltip contentStyle={{
              background: '#121822', border: '1px solid #2a3a50', borderRadius: 10, color: '#e6edf3', fontSize: 12,
            }} />
            <Legend wrapperStyle={{ fontSize: 12, color: '#8b97a6' }} />
            <Bar yAxisId="left" dataKey="symptomCount" name="症狀筆數" fill="#5a6572" barSize={10} />
            <Line yAxisId="right" type="monotone" dataKey="emotion" name="情緒分數" stroke="#6ea8ff" strokeWidth={2} dot={{ r: 2 }} />
            <Line yAxisId="right" type="monotone" dataKey="adherence" name="服藥順從率 %" stroke="#3ddc97" strokeWidth={2} dot={{ r: 2 }} />
            {lineEvents.map((e, i) => (
              <ReferenceLine
                key={i}
                yAxisId="left"
                x={e.label}
                stroke={CHANGE_COLOR[e.c.change_type] || '#9a7bff'}
                strokeDasharray="4 3"
                label={{
                  value: CHANGE_LABEL[e.c.change_type] || e.c.change_type,
                  fill: CHANGE_COLOR[e.c.change_type] || '#9a7bff',
                  fontSize: 10,
                  position: 'top',
                }}
              />
            ))}
          </ComposedChart>
        </ResponsiveContainer>
      </div>

      <div className="card">
        <h3 className="section-h">調藥前後 7 天對照</h3>
        {compares.length === 0 ? (
          <p className="cell-dim">尚無調藥紀錄</p>
        ) : (
          <table className="data-table">
            <thead>
              <tr>
                <th>日期</th>
                <th>類型</th>
                <th>內容</th>
                <th style={{ width: 130 }}>症狀（前→後）</th>
                <th style={{ width: 130 }}>情緒（前→後）</th>
                <th style={{ width: 130 }}>服藥率（前→後）</th>
              </tr>
            </thead>
            <tbody>
              {compares.map((cmp, i) => {
                const c = cmp.change
                const date = ((c.effective_date ?? c.created_at) || '').slice(0, 10)
                return (
                  <tr key={i}>
                    <td className="cell-strong">{date}</td>
                    <td>
                      <span className="badge" style={{ borderColor: CHANGE_COLOR[c.change_type] + '55', color: CHANGE_COLOR[c.change_type] }}>
                        {CHANGE_LABEL[c.change_type] || c.change_type}
                      </span>
                    </td>
                    <td className="cell-dim" style={{ fontSize: 12.5 }}>
                      {[
                        c.previous_dosage && `原 ${c.previous_dosage}`,
                        c.new_dosage && `新 ${c.new_dosage}`,
                        c.reason,
                      ].filter(Boolean).join(' · ') || '—'}
                    </td>
                    <CompareCell before={cmp.before.symptomTotal} after={cmp.after.symptomTotal} unit="筆" lowerBetter />
                    <CompareCell before={cmp.before.emotionAvg} after={cmp.after.emotionAvg} unit="分" />
                    <CompareCell before={cmp.before.adherenceAvg} after={cmp.after.adherenceAvg} unit="%" />
                  </tr>
                )
              })}
            </tbody>
          </table>
        )}
      </div>
    </>
  )
}

function CompareCell({ before, after, unit, lowerBetter }) {
  if (before == null && after == null) return <td className="cell-dim">—</td>
  const b = before == null ? '—' : `${before}`
  const a = after == null ? '—' : `${after}`
  let arrow = '→'
  let color = 'var(--text-dim)'
  if (before != null && after != null) {
    if (after > before) { arrow = '↑'; color = lowerBetter ? 'var(--err)' : 'var(--ok)' }
    else if (after < before) { arrow = '↓'; color = lowerBetter ? 'var(--ok)' : 'var(--err)' }
  }
  return (
    <td>
      <span style={{ color: 'var(--text-dim)' }}>{b}{unit}</span>
      <span style={{ margin: '0 6px', color }}>{arrow}</span>
      <span style={{ color: 'var(--text)', fontWeight: 600 }}>{a}{unit}</span>
    </td>
  )
}

function window7(series, ts, dir) {
  // dir = +7 取後 7 天；-7 取前 7 天（含當天）
  const dayMs = 86400_000
  const start = dir > 0 ? ts : ts + dir * dayMs
  const end = dir > 0 ? ts + dir * dayMs : ts
  let symptomTotal = 0
  let emotionSum = 0, emotionN = 0
  let adhSum = 0, adhN = 0
  for (const s of series) {
    const t = new Date(s.date).getTime()
    if (t < start || t > end) continue
    symptomTotal += s.symptomCount || 0
    if (s.emotion != null) { emotionSum += s.emotion; emotionN += 1 }
    if (s.adherence != null) { adhSum += s.adherence; adhN += 1 }
  }
  return {
    symptomTotal,
    emotionAvg: emotionN ? Math.round(emotionSum / emotionN) : null,
    adherenceAvg: adhN ? Math.round(adhSum / adhN) : null,
  }
}
