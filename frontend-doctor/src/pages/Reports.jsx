import { useEffect, useMemo, useState } from 'react'
import { apiGet } from '../lib/api.js'
import { fetchAllPatients } from '../lib/patients.js'
import TrendChart from '../components/TrendChart.jsx'

const RANGES = [
  { key: 7, label: '7 天' },
  { key: 30, label: '30 天' },
  { key: 90, label: '90 天' },
]

export default function Reports() {
  const [patients, setPatients] = useState([])
  const [patientId, setPatientId] = useState('')
  const [days, setDays] = useState(30)
  const [emotion, setEmotion] = useState([])
  const [medStats, setMedStats] = useState(null)
  const [loading, setLoading] = useState(false)
  const [err, setErr] = useState(null)

  useEffect(() => {
    fetchAllPatients()
      .then((ps) => {
        setPatients(ps)
        if (ps.length && !patientId) setPatientId(ps[0].id)
      })
      .catch((e) => setErr(e.message))
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  useEffect(() => {
    if (!patientId) return
    setLoading(true)
    setErr(null)
    Promise.all([
      apiGet('/emotions/trend', { patient_id: patientId, days }),
      apiGet('/medications/stats', { patient_id: patientId, days }).catch(() => null),
    ])
      .then(([em, ms]) => {
        setEmotion(em.trend ?? [])
        setMedStats(ms)
      })
      .catch((e) => setErr(e.message))
      .finally(() => setLoading(false))
  }, [patientId, days])

  const emotionData = useMemo(() => {
    const byDay = new Map()
    for (const e of emotion) {
      if (!e.date || e.score == null) continue
      const cur = byDay.get(e.date) ?? { sum: 0, n: 0 }
      cur.sum += e.score * 20
      cur.n += 1
      byDay.set(e.date, cur)
    }
    return [...byDay.entries()]
      .sort(([a], [b]) => a.localeCompare(b))
      .map(([d, v]) => {
        const md = new Date(d)
        return {
          date: `${md.getMonth() + 1}/${md.getDate()}`,
          emotion: Math.round(v.sum / v.n),
        }
      })
  }, [emotion])

  const adherenceData = useMemo(() => {
    return (medStats?.adherence_trend ?? []).map((a) => {
      const md = new Date(a.date)
      return {
        date: `${md.getMonth() + 1}/${md.getDate()}`,
        adherence: a.rate,
      }
    })
  }, [medStats])

  const selected = patients.find((p) => p.id === patientId)

  return (
    <>
      <h1 className="page-title">整合報告</h1>
      <p className="page-sub">
        每位患者每日情緒（1-5 換算 0-100）與服藥順從率，皆來自患者端寫入的紀錄。
      </p>

      <div className="toolbar">
        <select
          className="text-input"
          value={patientId}
          onChange={(e) => setPatientId(e.target.value)}
        >
          {patients.length === 0 && <option value="">尚無患者</option>}
          {patients.map((p) => (
            <option key={p.id} value={p.id}>
              {p.name}{p.age != null ? `（${p.age} 歲）` : ''}{p.username ? ` · @${p.username}` : ''}
            </option>
          ))}
        </select>
        <div className="range-tabs">
          {RANGES.map((r) => (
            <button
              key={r.key}
              className={`range-tab ${days === r.key ? 'active' : ''}`}
              onClick={() => setDays(r.key)}
            >
              {r.label}
            </button>
          ))}
        </div>
      </div>

      {err && <div className="error-bar">{err}</div>}

      {selected && (
        <div className="profile-grid">
          <div className="card mini">
            <p className="card-title">服藥順從率</p>
            <div className="card-value">
              {medStats?.summary?.adherence_rate != null ? `${medStats.summary.adherence_rate}%` : '—'}
            </div>
          </div>
          <div className="card mini">
            <p className="card-title">情緒評分數</p>
            <div className="card-value">{emotion.length}</div>
          </div>
          <div className="card mini">
            <p className="card-title">用藥種類</p>
            <div className="card-value">{medStats?.summary?.total_medications ?? '—'}</div>
          </div>
          <div className="card mini">
            <p className="card-title">服藥日誌數</p>
            <div className="card-value">{medStats?.summary?.total_logs ?? '—'}</div>
          </div>
        </div>
      )}

      <div className="chart-card" style={{ marginBottom: 16 }}>
        <div className="chart-header">
          <div>
            <h2 className="chart-title">情緒趨勢</h2>
            <p className="chart-sub">換算為 0-100 分（=患者每日 1-5 評分 × 20）</p>
          </div>
        </div>
        {emotionData.length > 0 ? (
          <TrendChart data={emotionData} lines={['emotion']} height={260} />
        ) : (
          <div className="placeholder">{loading ? '載入中…' : '此期間尚無情緒紀錄'}</div>
        )}
      </div>

      <div className="chart-card">
        <div className="chart-header">
          <div>
            <h2 className="chart-title">服藥順從率</h2>
            <p className="chart-sub">每日打卡完成比例（%）</p>
          </div>
        </div>
        {adherenceData.length > 0 ? (
          <TrendChart data={adherenceData} lines={['adherence']} height={260} />
        ) : (
          <div className="placeholder">{loading ? '載入中…' : '此期間尚無服藥日誌'}</div>
        )}
      </div>
    </>
  )
}
