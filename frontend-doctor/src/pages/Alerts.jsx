import { useEffect, useState } from 'react'
import { apiGet, apiPut } from '../lib/api.js'

const TYPE_LABEL = {
  er_visit: '急診觸發',
  missed_medication: '連續漏藥',
  self_discontinued: '自行停藥',
  infection: '感染徵兆',
  low_mood: '情緒低落',
  psych_crisis: '心理危機（靜默守護）',
  other: '其他',
}

const SEV_BADGE = {
  critical: 'crit',
  high: 'err',
  medium: 'warn',
  low: 'ok',
}

export default function Alerts() {
  const [alerts, setAlerts] = useState([])
  const [loading, setLoading] = useState(true)

  function refresh() {
    setLoading(true)
    apiGet('/alerts/?resolved=false')
      .then((d) => setAlerts(d.alerts || []))
      .finally(() => setLoading(false))
  }

  useEffect(refresh, [])

  async function ack(id) {
    await apiPut(`/alerts/${id}`, { acknowledged: true })
    refresh()
  }
  async function resolve(id) {
    await apiPut(`/alerts/${id}`, { resolved: true })
    refresh()
  }

  return (
    <>
      <h1 className="page-title">警示</h1>
      <p className="page-sub">急診 · 漏藥 · 自行停藥 · 感染 · 情緒低落 · 心理危機（靜默守護）</p>

      {loading && <p className="page-sub">載入中…</p>}

      <div className="card" style={{ padding: 0 }}>
        <table style={{ width: '100%', borderCollapse: 'collapse' }}>
          <thead>
            <tr style={{ color: 'var(--text-dim)', fontSize: 12, textTransform: 'uppercase' }}>
              <th style={th}>等級</th>
              <th style={th}>類型</th>
              <th style={th}>標題</th>
              <th style={th}>建立時間</th>
              <th style={th}>動作</th>
            </tr>
          </thead>
          <tbody>
            {alerts.map((a) => (
              <tr key={a.id} style={{ borderTop: '1px solid var(--border)' }}>
                <td style={td}>
                  <span className={`badge ${SEV_BADGE[a.severity] || 'ok'}`}>{a.severity}</span>
                </td>
                <td style={td}>{TYPE_LABEL[a.alert_type] || a.alert_type}</td>
                <td style={td}>
                  <strong>{a.title}</strong>
                  {a.detail && (
                    <div style={{ fontSize: 12, color: 'var(--text-dim)', marginTop: 4 }}>{a.detail}</div>
                  )}
                </td>
                <td style={{ ...td, color: 'var(--text-dim)', fontSize: 12 }}>
                  {(a.created_at || '').slice(0, 16).replace('T', ' ')}
                </td>
                <td style={td}>
                  {!a.acknowledged && (
                    <button onClick={() => ack(a.id)} style={btnSmall}>已知悉</button>
                  )}
                  <button onClick={() => resolve(a.id)} style={{ ...btnSmall, marginLeft: 4 }}>
                    處理完成
                  </button>
                </td>
              </tr>
            ))}
            {!loading && !alerts.length && (
              <tr>
                <td colSpan={5} style={{ ...td, textAlign: 'center', color: 'var(--text-faint)' }}>
                  目前無未處理警示
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </>
  )
}

const th = { textAlign: 'left', padding: '14px 20px', fontWeight: 600 }
const td = { padding: '14px 20px', fontSize: 14, verticalAlign: 'top' }
const btnSmall = {
  padding: '4px 10px',
  fontSize: 12,
  border: '1px solid var(--border)',
  background: 'var(--bg)',
  borderRadius: 4,
  cursor: 'pointer',
}
