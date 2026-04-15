import { useMemo, useState } from 'react'
import { generateTrendData } from '../lib/mockData.js'
import TrendChart from '../components/TrendChart.jsx'

const RANGES = [
  { key: 7, label: '7 天' },
  { key: 30, label: '30 天' },
  { key: 90, label: '90 天' },
]

export default function Reports() {
  const [range, setRange] = useState(30)
  const data = useMemo(() => generateTrendData(range), [range])

  return (
    <>
      <h1 className="page-title">整合報告</h1>
      <p className="page-sub">
        Phase 4 · 三十天整合報告（LLM 文字摘要 + 多張折線圖將接上患者資料）
      </p>

      <div className="chart-card" style={{ marginBottom: 16 }}>
        <div className="chart-header">
          <div>
            <h2 className="chart-title">情緒趨勢</h2>
            <p className="chart-sub">每日情緒分數（0-100）</p>
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
        <TrendChart data={data} lines={['emotion']} height={260} />
      </div>

      <div className="chart-card" style={{ marginBottom: 16 }}>
        <div className="chart-header">
          <div>
            <h2 className="chart-title">症狀嚴重度</h2>
            <p className="chart-sub">綜合症狀打分（0-100）</p>
          </div>
        </div>
        <TrendChart data={data} lines={['symptom']} height={260} />
      </div>

      <div className="chart-card">
        <div className="chart-header">
          <div>
            <h2 className="chart-title">服藥順從率</h2>
            <p className="chart-sub">每日服藥完成比例</p>
          </div>
        </div>
        <TrendChart data={data} lines={['adherence']} height={260} />
      </div>
    </>
  )
}
