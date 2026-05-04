import { useMemo } from 'react'
import {
  ResponsiveContainer, LineChart, Line, XAxis, YAxis, CartesianGrid,
  Tooltip, Legend, ReferenceLine,
} from 'recharts'

// 把同一指標切成「上次回診前 N 天」「這次回診前 N 天」兩段
// 對齊到「相對天數」（-N..0）疊在同一圖上比對
const WINDOW_DAYS = 14

function buildWindow(items, ts, getDateStr, getValue) {
  const start = ts - WINDOW_DAYS * 86400_000
  const end = ts
  const map = new Map()
  for (const it of items || []) {
    const d = getDateStr(it)
    if (!d) continue
    const t = new Date(d).getTime()
    if (Number.isNaN(t) || t < start || t > end) continue
    const offset = Math.round((t - end) / 86400_000) // -14..0
    const v = getValue(it)
    if (v == null) continue
    const cur = map.get(offset) ?? { sum: 0, n: 0 }
    cur.sum += v
    cur.n += 1
    map.set(offset, cur)
  }
  return map
}

export default function VisitLineCompare({ previous, current, emotionTrend, medStats, symptoms }) {
  const data = useMemo(() => {
    const prevTs = new Date(previous.visit_date ?? previous.created_at).getTime()
    const curTs = new Date(current.visit_date ?? current.created_at).getTime()
    if (Number.isNaN(prevTs) || Number.isNaN(curTs)) return []

    // 情緒（按日聚合，分數×20 對到 0-100）
    const prevEmo = buildWindow(emotionTrend, prevTs, (e) => e.date, (e) => e.score != null ? e.score * 20 : null)
    const curEmo = buildWindow(emotionTrend, curTs, (e) => e.date, (e) => e.score != null ? e.score * 20 : null)
    // 服藥率
    const prevAdh = buildWindow(medStats?.adherence_trend, prevTs, (a) => a.date, (a) => a.rate)
    const curAdh = buildWindow(medStats?.adherence_trend, curTs, (a) => a.date, (a) => a.rate)
    // 症狀數
    const prevSym = buildWindow(
      (symptoms || []).map((s) => ({
        date: (s.created_at || '').slice(0, 10),
        n: Array.isArray(s.symptoms) ? s.symptoms.length : 0,
      })),
      prevTs, (x) => x.date, (x) => x.n,
    )
    const curSym = buildWindow(
      (symptoms || []).map((s) => ({
        date: (s.created_at || '').slice(0, 10),
        n: Array.isArray(s.symptoms) ? s.symptoms.length : 0,
      })),
      curTs, (x) => x.date, (x) => x.n,
    )

    const out = []
    for (let d = -WINDOW_DAYS; d <= 0; d += 1) {
      const row = { dayOffset: d, label: d === 0 ? '回診當天' : `D${d}` }
      const pe = prevEmo.get(d); if (pe) row.prevEmotion = Math.round(pe.sum / pe.n)
      const ce = curEmo.get(d); if (ce) row.curEmotion = Math.round(ce.sum / ce.n)
      const pa = prevAdh.get(d); if (pa) row.prevAdherence = Math.round(pa.sum / pa.n)
      const ca = curAdh.get(d); if (ca) row.curAdherence = Math.round(ca.sum / ca.n)
      const ps = prevSym.get(d); if (ps) row.prevSymptoms = ps.sum
      const cs = curSym.get(d); if (cs) row.curSymptoms = cs.sum
      out.push(row)
    }
    return out
  }, [previous, current, emotionTrend, medStats, symptoms])

  const hasAny = data.some((r) =>
    r.prevEmotion != null || r.curEmotion != null ||
    r.prevAdherence != null || r.curAdherence != null ||
    r.prevSymptoms != null || r.curSymptoms != null,
  )

  if (!hasAny) {
    return (
      <p className="cell-dim" style={{ marginTop: 8, fontSize: 13 }}>
        近兩次回診前 {WINDOW_DAYS} 天皆無可比對資料。
      </p>
    )
  }

  return (
    <div style={{ marginTop: 12 }}>
      <p className="cell-dim" style={{ marginBottom: 10, fontSize: 12.5 }}>
        橫軸＝距回診天數（D-{WINDOW_DAYS} 到 D0），同色實線=這次、虛線=上次。
      </p>
      <ResponsiveContainer width="100%" height={300}>
        <LineChart data={data} margin={{ top: 8, right: 16, left: -8, bottom: 0 }}>
          <CartesianGrid stroke="#1e2a3a" strokeDasharray="3 3" vertical={false} />
          <XAxis dataKey="label" tick={{ fill: '#8b97a6', fontSize: 11 }} tickLine={false} axisLine={{ stroke: '#1e2a3a' }} />
          <YAxis yAxisId="left" tick={{ fill: '#8b97a6', fontSize: 11 }} tickLine={false} axisLine={{ stroke: '#1e2a3a' }} />
          <YAxis yAxisId="right" orientation="right" tick={{ fill: '#8b97a6', fontSize: 11 }} tickLine={false} axisLine={{ stroke: '#1e2a3a' }} />
          <Tooltip contentStyle={{ background: '#121822', border: '1px solid #2a3a50', borderRadius: 10, color: '#e6edf3', fontSize: 12 }} />
          <Legend wrapperStyle={{ fontSize: 12, color: '#8b97a6' }} />
          <ReferenceLine yAxisId="left" x="回診當天" stroke="#5a6572" strokeDasharray="2 4" />

          <Line yAxisId="left" type="monotone" dataKey="prevEmotion" name="情緒（上次）" stroke="#6ea8ff" strokeWidth={2} strokeDasharray="5 4" dot={false} connectNulls />
          <Line yAxisId="left" type="monotone" dataKey="curEmotion"  name="情緒（這次）" stroke="#6ea8ff" strokeWidth={2.5} dot={{ r: 2.5 }} connectNulls />

          <Line yAxisId="left" type="monotone" dataKey="prevAdherence" name="服藥率%（上次）" stroke="#3ddc97" strokeWidth={2} strokeDasharray="5 4" dot={false} connectNulls />
          <Line yAxisId="left" type="monotone" dataKey="curAdherence"  name="服藥率%（這次）" stroke="#3ddc97" strokeWidth={2.5} dot={{ r: 2.5 }} connectNulls />

          <Line yAxisId="right" type="monotone" dataKey="prevSymptoms" name="症狀數（上次）" stroke="#ff6b81" strokeWidth={2} strokeDasharray="5 4" dot={false} connectNulls />
          <Line yAxisId="right" type="monotone" dataKey="curSymptoms"  name="症狀數（這次）" stroke="#ff6b81" strokeWidth={2.5} dot={{ r: 2.5 }} connectNulls />
        </LineChart>
      </ResponsiveContainer>
    </div>
  )
}
