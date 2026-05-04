import { useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { apiGet } from '../lib/api.js'
import { fetchAllPatients } from '../lib/patients.js'
import { patientPriority, ALERT_TYPE_LABEL } from '../lib/priority.js'
import { fmtShort } from '../lib/format.js'

const FILTERS = [
  { key: 'all', label: '全部' },
  { key: 'attention', label: '需關注' },
  { key: 'stable', label: '穩定' },
]

export default function PatientList() {
  const [patients, setPatients] = useState([])
  const [alertsByPatient, setAlertsByPatient] = useState({})
  const [loading, setLoading] = useState(true)
  const [err, setErr] = useState(null)
  const [filter, setFilter] = useState('all')
  const [search, setSearch] = useState('')

  useEffect(() => {
    let alive = true
    Promise.all([
      fetchAllPatients(),
      apiGet('/alerts/', { resolved: false }).catch(() => ({ alerts: [] })),
    ])
      .then(([ps, a]) => {
        if (!alive) return
        setPatients(ps)
        const map = {}
        for (const al of a.alerts ?? []) {
          if (!map[al.patient_id]) map[al.patient_id] = []
          map[al.patient_id].push(al)
        }
        setAlertsByPatient(map)
      })
      .catch((e) => alive && setErr(e.message))
      .finally(() => alive && setLoading(false))
    return () => {
      alive = false
    }
  }, [])

  const rows = useMemo(() => {
    const enriched = patients.map((p) => {
      const alerts = alertsByPatient[p.id] ?? []
      const prio = patientPriority(alerts)
      return { ...p, _alerts: alerts, _prio: prio }
    })
    enriched.sort((a, b) => {
      if (b._prio.rank !== a._prio.rank) return b._prio.rank - a._prio.rank
      return (a.name ?? '').localeCompare(b.name ?? '', 'zh-Hant')
    })
    return enriched
  }, [patients, alertsByPatient])

  const filtered = useMemo(() => {
    let r = rows
    if (filter === 'attention') r = r.filter((x) => x._prio.rank > 0)
    if (filter === 'stable') r = r.filter((x) => x._prio.rank === 0)
    if (search.trim()) {
      const q = search.trim().toLowerCase()
      r = r.filter((x) =>
        (x.name ?? '').toLowerCase().includes(q) ||
        (x.username ?? '').toLowerCase().includes(q) ||
        (x.phone ?? '').toLowerCase().includes(q) ||
        (x.id ?? '').toLowerCase().includes(q)
      )
    }
    return r
  }, [rows, filter, search])

  const counts = useMemo(() => {
    const attention = rows.filter((x) => x._prio.rank > 0).length
    return { total: rows.length, attention, stable: rows.length - attention }
  }, [rows])

  return (
    <>
      <div className="page-head-row">
        <div>
          <h1 className="page-title">患者清單</h1>
          <p className="page-sub">依未處理警示的嚴重度自動排序</p>
        </div>
        <div className="page-stats">
          <span><strong>{counts.total}</strong> 位追蹤中</span>
          <span className="dot" />
          <span style={{ color: 'var(--err)' }}><strong>{counts.attention}</strong> 需關注</span>
        </div>
      </div>

      <div className="toolbar">
        <div className="range-tabs">
          {FILTERS.map((f) => (
            <button
              key={f.key}
              className={`range-tab ${filter === f.key ? 'active' : ''}`}
              onClick={() => setFilter(f.key)}
            >
              {f.label}
            </button>
          ))}
        </div>
        <input
          className="text-input"
          placeholder="搜尋姓名、帳號、電話或 ID"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
        />
      </div>

      {err && <div className="error-bar">{err}</div>}

      <div className="card" style={{ padding: 0 }}>
        <table className="data-table">
          <thead>
            <tr>
              <th style={{ width: 140 }}>狀態</th>
              <th>姓名</th>
              <th style={{ width: 80 }}>年齡</th>
              <th style={{ width: 90 }}>性別</th>
              <th style={{ width: 110 }}>建檔</th>
              <th>主要警示</th>
            </tr>
          </thead>
          <tbody>
            {loading && (
              <tr><td colSpan={6} style={{ padding: 24, textAlign: 'center', color: 'var(--text-dim)' }}>載入中…</td></tr>
            )}
            {!loading && filtered.length === 0 && (
              <tr><td colSpan={6} style={{ padding: 24, textAlign: 'center', color: 'var(--text-dim)' }}>
                {patients.length === 0 ? '尚無患者資料' : '沒有符合條件的患者'}
              </td></tr>
            )}
            {filtered.map((p) => {
              const a = p._prio.alert
              return (
                <tr key={p.id}>
                  <td><span className={`badge ${p._prio.badge}`}>{p._prio.label}</span></td>
                  <td className="cell-strong">
                    <Link to={`/patients/${p.id}`} className="row-link">{p.name ?? '（未命名）'}</Link>
                  </td>
                  <td>{p.age ?? '—'}</td>
                  <td className="cell-dim">{p.gender ?? '—'}</td>
                  <td className="cell-dim">{fmtShort(p.created_at)}</td>
                  <td className="cell-dim">
                    {a ? (
                      <>
                        <strong style={{ color: 'var(--text)' }}>
                          {ALERT_TYPE_LABEL[a.alert_type] ?? a.alert_type}
                        </strong>
                        {a.title ? ` · ${a.title}` : ''}
                      </>
                    ) : (
                      '無未處理警示'
                    )}
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>
    </>
  )
}
