import { useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { apiGet, getApiBase } from '../lib/api.js'
import {
  ALERT_TYPE_LABEL, SEVERITY_TO_BADGE, SEVERITY_LABEL, SEVERITY_RANK,
} from '../lib/priority.js'
import { isToday, relativeTime } from '../lib/format.js'

export default function Dashboard() {
  const [backend, setBackend] = useState({ status: '連線中…', ok: null })
  const [patients, setPatients] = useState([])
  const [openAlerts, setOpenAlerts] = useState([])
  const [allAlerts, setAllAlerts] = useState([])
  const [notes, setNotes] = useState([])
  const [err, setErr] = useState(null)
  const [nowRef] = useState(() => Date.now())

  useEffect(() => {
    let alive = true
    Promise.all([
      apiGet('/patients/'),
      apiGet('/alerts/', { resolved: false }),
      apiGet('/alerts/'),
      apiGet('/doctor-notes/'),
    ])
      .then(([p, oa, a, n]) => {
        if (!alive) return
        setPatients(p.patients ?? [])
        setOpenAlerts(oa.alerts ?? [])
        setAllAlerts(a.alerts ?? [])
        setNotes(n.notes ?? [])
        setBackend({ status: `已連線 · ${getApiBase()}`, ok: true })
      })
      .catch((e) => {
        if (!alive) return
        setErr(e.message)
        setBackend({ status: `離線：${e.message}`, ok: false })
      })
    return () => { alive = false }
  }, [])

  const summary = useMemo(() => {
    const today = (allAlerts ?? []).filter((a) => isToday(a.created_at)).length
    const critical = openAlerts.filter((a) => a.severity === 'critical' || a.severity === 'high').length
    const cutoff = nowRef - 7 * 24 * 3600 * 1000
    const recentNotes = notes.filter((n) => {
      const d = new Date(n.created_at)
      return d.getTime() >= cutoff
    }).length
    return {
      activePatients: patients.length,
      openAlerts: openAlerts.length,
      criticalAlerts: critical,
      todayAlerts: today,
      notesRecent: recentNotes,
    }
  }, [patients, openAlerts, allAlerts, notes, nowRef])

  const topAlerts = useMemo(() => {
    return [...openAlerts]
      .sort((a, b) =>
        (SEVERITY_RANK[b.severity] ?? 0) - (SEVERITY_RANK[a.severity] ?? 0) ||
        new Date(b.created_at) - new Date(a.created_at)
      )
      .slice(0, 6)
  }, [openAlerts])

  const patientById = useMemo(() => {
    const m = {}
    for (const p of patients) m[p.id] = p
    return m
  }, [patients])

  const badgeClass = backend.ok === true ? 'ok' : backend.ok === false ? 'err' : ''

  return (
    <>
      <div className="page-head-row">
        <div>
          <h1 className="page-title">儀表板</h1>
          <p className="page-sub">所有追蹤中患者的整體狀態概覽</p>
        </div>
        <span className={`badge ${badgeClass}`}>{backend.status}</span>
      </div>

      {err && <div className="error-bar">{err}</div>}

      <div className="summary-grid">
        <div className="card">
          <p className="card-title">追蹤中患者</p>
          <div className="card-value">{summary.activePatients}</div>
          <div className="card-delta">
            <Link to="/patients" className="row-link">查看清單 →</Link>
          </div>
        </div>
        <div className="card">
          <p className="card-title">未處理警示</p>
          <div className="card-value" style={{ color: summary.openAlerts ? 'var(--err)' : 'var(--text)' }}>
            {summary.openAlerts}
          </div>
          <div className="card-delta warn">
            {summary.criticalAlerts ? `${summary.criticalAlerts} 件高優先` : '無高優先警示'}
          </div>
        </div>
        <div className="card">
          <p className="card-title">今日新警示</p>
          <div className="card-value">{summary.todayAlerts}</div>
          <div className="card-delta">
            <Link to="/alerts" className="row-link">前往警示 →</Link>
          </div>
        </div>
        <div className="card">
          <p className="card-title">近 7 日備註</p>
          <div className="card-value">{summary.notesRecent}</div>
          <div className="card-delta">含所有醫師</div>
        </div>
      </div>

      <div className="card">
        <h3 className="section-h">最需關注的警示</h3>
        {topAlerts.length === 0 ? (
          <p className="cell-dim">目前沒有未處理警示</p>
        ) : (
          <ul className="bullet-list">
            {topAlerts.map((a) => {
              const p = patientById[a.patient_id]
              return (
                <li key={a.id}>
                  <span className={`badge ${SEVERITY_TO_BADGE[a.severity] ?? 'warn'}`}>
                    {SEVERITY_LABEL[a.severity] ?? a.severity}
                  </span>
                  {' '}
                  <strong>{ALERT_TYPE_LABEL[a.alert_type] ?? a.alert_type}</strong>
                  {' · '}
                  {p ? (
                    <Link to={`/patients/${p.id}`} className="row-link">{p.name}</Link>
                  ) : (
                    <span className="cell-dim">{a.patient_id?.slice(0, 8)}</span>
                  )}
                  {' · '}
                  <span className="cell-dim">{a.title}</span>
                  {' · '}
                  <span className="cell-dim">{relativeTime(a.created_at)}</span>
                </li>
              )
            })}
          </ul>
        )}
      </div>
    </>
  )
}
