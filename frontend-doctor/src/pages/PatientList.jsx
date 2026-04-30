import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { apiGet } from '../lib/api.js'

const PRIORITY_LABEL = {
  needs_immediate_attention: '需立即關注',
  needs_attention: '需要關注',
  stable: '狀況穩定',
}

const PRIORITY_BADGE = {
  needs_immediate_attention: 'crit',
  needs_attention: 'warn',
  stable: 'ok',
}

export default function PatientList() {
  const [patients, setPatients] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  useEffect(() => {
    apiGet('/doctor-dashboard/priority')
      .then((d) => setPatients(d.patients || []))
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false))
  }, [])

  return (
    <>
      <h1 className="page-title">患者清單</h1>
      <p className="page-sub">依需要關注程度自動排序（個人化基準線比對）</p>

      {loading && <p className="page-sub">載入中…</p>}
      {error && <p className="page-sub" style={{ color: 'var(--err)' }}>連線失敗：{error}</p>}

      <div className="card" style={{ padding: 0 }}>
        <table style={{ width: '100%', borderCollapse: 'collapse' }}>
          <thead>
            <tr style={{ color: 'var(--text-dim)', fontSize: 12, textTransform: 'uppercase', letterSpacing: 1 }}>
              <th style={th}>狀態</th>
              <th style={th}>姓名</th>
              <th style={th}>年齡</th>
              <th style={th}>未處理警示</th>
              <th style={th}>本期重點</th>
            </tr>
          </thead>
          <tbody>
            {patients.map((p) => (
              <tr key={p.patient_id} style={{ borderTop: '1px solid var(--border)' }}>
                <td style={td}>
                  <span className={`badge ${PRIORITY_BADGE[p.priority] || 'ok'}`}>
                    {PRIORITY_LABEL[p.priority] || p.priority}
                  </span>
                </td>
                <td style={{ ...td, fontWeight: 600 }}>
                  <Link to={`/patients/${p.patient_id}`}>{p.patient_name || '匿名'}</Link>
                </td>
                <td style={td}>{p.age ?? '—'}</td>
                <td style={td}>
                  {p.alerts_count > 0 ? (
                    <span style={{ color: p.critical_alerts_count ? 'var(--err)' : 'var(--text-dim)' }}>
                      {p.alerts_count}（高 {p.critical_alerts_count}）
                    </span>
                  ) : (
                    <span style={{ color: 'var(--text-faint)' }}>無</span>
                  )}
                </td>
                <td style={{ ...td, color: 'var(--text-dim)' }}>{p.reason}</td>
              </tr>
            ))}
            {!loading && !patients.length && (
              <tr>
                <td colSpan={5} style={{ ...td, textAlign: 'center', color: 'var(--text-faint)' }}>
                  尚無追蹤中的患者
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
const td = { padding: '14px 20px', fontSize: 14 }
