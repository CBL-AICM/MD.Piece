import { useEffect, useState, useMemo } from 'react'
import { apiGet } from '../lib/api.js'
import { generateTrendData, mockSummary } from '../lib/mockData.js'
import TrendChart from '../components/TrendChart.jsx'

const RANGES = [
  { key: 7, label: '7 天' },
  { key: 30, label: '30 天' },
  { key: 90, label: '90 天' },
]

export default function Dashboard() {
  const [backend, setBackend] = useState({ status: '連線中…', ok: null })
  const [range, setRange] = useState(30)
  const data = useMemo(() => generateTrendData(range), [range])

  useEffect(() => {
    apiGet('/doctors/')
      .then((d) =>
        setBackend({ status: `已連線 · 醫師 ${d.doctors?.length ?? 0} 位`, ok: true })
      )
      .catch((e) => setBackend({ status: `離線：${e.message}`, ok: false }))
  }, [])

  const badgeClass = backend.ok === true ? 'ok' : backend.ok === false ? 'err' : ''

  return (
    <>
      <div style={{ display: 'flex', alignItems: 'baseline', justifyContent: 'space-between', marginBottom: 4 }}>
        <h1 className="page-title">儀表板</h1>
        <span className={`badge ${badgeClass}`}>{backend.status}</span>
      </div>
      <p className="page-sub">所有追蹤中患者的整體狀態概覽</p>

      <div className="summary-grid">
        <div className="card">
          <p className="card-title">追蹤中患者</p>
          <div className="card-value">{mockSummary.activePatients}</div>
          <div className="card-delta ok">↑ 較上週 +2</div>
        </div>
        <div className="card">
          <p className="card-title">今日警示</p>
          <div className="card-value" style={{ color: 'var(--err)' }}>
            {mockSummary.alertsToday}
          </div>
          <div className="card-delta warn">1 件需立即處理</div>
        </div>
        <div className="card">
          <p className="card-title">待寫備註</p>
          <div className="card-value">{mockSummary.pendingNotes}</div>
          <div className="card-delta">近 7 日回診</div>
        </div>
        <div className="card">
          <p className="card-title">平均服藥順從率</p>
          <div className="card-value">{mockSummary.avgAdherence}%</div>
          <div className="card-delta ok">↑ 較上週 +3%</div>
        </div>
      </div>

      <div className="chart-card">
        <div className="chart-header">
          <div>
            <h2 className="chart-title">整體趨勢</h2>
            <p className="chart-sub">情緒 · 症狀嚴重度 · 服藥順從率（所有患者平均）</p>
          </div>
          <div className="range-tabs">
            {RANGES.map((r) => (
              <button
                key={r.key}
                className={`range-tab ${range === r.key ? 'active' : ''}`}
                onClick={() => setRange(r.key)}
              >
                {r.label}
              </button>
            ))}
          </div>
        </div>
        <TrendChart data={data} height={340} />
        <p style={{ marginTop: 12, fontSize: 12, color: 'var(--text-faint)' }}>
          * 目前為示範資料，接上患者資料後自動切換
        </p>
      </div>
    </>
  )
}
