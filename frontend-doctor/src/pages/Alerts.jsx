import { useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { apiGet, apiPut, getActiveDoctorId } from '../lib/api.js'
import {
  ALERT_TYPE_LABEL,
  SEVERITY_LABEL,
  SEVERITY_RANK,
  SEVERITY_TO_BADGE,
} from '../lib/priority.js'
import { fmtDate, relativeTime } from '../lib/format.js'

const STATUS_TABS = [
  { key: 'open', label: '未處理', filter: { resolved: false } },
  { key: 'ack', label: '已確認', filter: { acknowledged: true, resolved: false } },
  { key: 'resolved', label: '已結案', filter: { resolved: true } },
  { key: 'all', label: '全部', filter: {} },
]

const SEVERITIES = [
  { key: 'all', label: '所有嚴重度' },
  { key: 'critical', label: 'Critical' },
  { key: 'high', label: 'High' },
  { key: 'medium', label: 'Medium' },
  { key: 'low', label: 'Low' },
]

export default function Alerts() {
  const [tab, setTab] = useState('open')
  const [severity, setSeverity] = useState('all')
  const [alerts, setAlerts] = useState([])
  const [patients, setPatients] = useState({})
  const [loading, setLoading] = useState(true)
  const [err, setErr] = useState(null)
  const [busyId, setBusyId] = useState(null)

  const load = async () => {
    setLoading(true)
    setErr(null)
    try {
      const tabConf = STATUS_TABS.find((t) => t.key === tab) ?? STATUS_TABS[0]
      const params = { ...tabConf.filter }
      if (severity !== 'all') params.severity = severity
      const [a, p] = await Promise.all([
        apiGet('/alerts/', params),
        apiGet('/patients/'),
      ])
      const map = {}
      for (const x of p.patients ?? []) map[x.id] = x
      setPatients(map)
      setAlerts(a.alerts ?? [])
    } catch (e) {
      setErr(e.message)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    load()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [tab, severity])

  const sorted = useMemo(() => {
    return [...alerts].sort((a, b) => {
      const r = (SEVERITY_RANK[b.severity] ?? 0) - (SEVERITY_RANK[a.severity] ?? 0)
      if (r !== 0) return r
      return new Date(b.created_at).getTime() - new Date(a.created_at).getTime()
    })
  }, [alerts])

  const acknowledge = async (id) => {
    setBusyId(id)
    try {
      await apiPut(`/alerts/${id}`, {
        acknowledged: true,
        acknowledged_by: getActiveDoctorId() || undefined,
      })
      await load()
    } catch (e) {
      setErr(e.message)
    } finally {
      setBusyId(null)
    }
  }

  const resolve = async (id) => {
    setBusyId(id)
    try {
      await apiPut(`/alerts/${id}`, { resolved: true })
      await load()
    } catch (e) {
      setErr(e.message)
    } finally {
      setBusyId(null)
    }
  }

  return (
    <>
      <h1 className="page-title">警示</h1>
      <p className="page-sub">急診 · 漏藥 · 自行停藥 · 感染 · 情緒低落 · 心理危機</p>

      <div className="toolbar">
        <div className="range-tabs">
          {STATUS_TABS.map((t) => (
            <button
              key={t.key}
              className={`range-tab ${tab === t.key ? 'active' : ''}`}
              onClick={() => setTab(t.key)}
            >
              {t.label}
            </button>
          ))}
        </div>
        <select
          className="text-input"
          value={severity}
          onChange={(e) => setSeverity(e.target.value)}
        >
          {SEVERITIES.map((s) => (
            <option key={s.key} value={s.key}>{s.label}</option>
          ))}
        </select>
      </div>

      {err && <div className="error-bar">{err}</div>}

      {loading && <div className="placeholder">載入中…</div>}

      {!loading && sorted.length === 0 && (
        <div className="placeholder">目前沒有符合條件的警示</div>
      )}

      <div className="alert-list">
        {sorted.map((a) => {
          const patient = patients[a.patient_id]
          const badge = SEVERITY_TO_BADGE[a.severity] ?? 'warn'
          return (
            <div key={a.id} className="alert-card">
              <div className="alert-card-head">
                <div>
                  <span className={`badge ${badge}`}>{SEVERITY_LABEL[a.severity] ?? a.severity}</span>
                  <span className="alert-type">{ALERT_TYPE_LABEL[a.alert_type] ?? a.alert_type}</span>
                </div>
                <div className="alert-meta">
                  {relativeTime(a.created_at)} · {fmtDate(a.created_at, true)}
                </div>
              </div>

              <h3 className="alert-title">{a.title}</h3>
              {a.detail && <p className="alert-detail">{a.detail}</p>}

              <div className="alert-foot">
                <div className="alert-patient">
                  {patient ? (
                    <Link to={`/patients/${patient.id}`} className="row-link">
                      {patient.name}
                    </Link>
                  ) : (
                    <span className="cell-dim">患者 {a.patient_id?.slice(0, 8) ?? '—'}</span>
                  )}
                  {patient?.age != null && <span className="cell-dim"> · {patient.age} 歲</span>}
                  {a.source && <span className="cell-dim"> · 來源：{a.source}</span>}
                </div>
                <div className="alert-actions">
                  {!a.acknowledged && !a.resolved && (
                    <button
                      className="btn"
                      disabled={busyId === a.id}
                      onClick={() => acknowledge(a.id)}
                    >
                      確認
                    </button>
                  )}
                  {!a.resolved && (
                    <button
                      className="btn btn-primary"
                      disabled={busyId === a.id}
                      onClick={() => resolve(a.id)}
                    >
                      結案
                    </button>
                  )}
                  {a.resolved && <span className="badge ok">已結案</span>}
                </div>
              </div>
            </div>
          )
        })}
      </div>
    </>
  )
}
