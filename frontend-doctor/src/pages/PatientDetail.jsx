import { useEffect, useState, useMemo } from 'react'
import { useParams, Link } from 'react-router-dom'
import {
  apiGet, apiPost, apiPut, apiDelete, getActiveDoctorId,
} from '../lib/api.js'
import { fetchPatientById } from '../lib/patients.js'
import {
  ALERT_TYPE_LABEL, SEVERITY_LABEL, SEVERITY_TO_BADGE, patientPriority,
} from '../lib/priority.js'
import { fmtDate, relativeTime } from '../lib/format.js'
import TrendChart from '../components/TrendChart.jsx'
import ChartsPanel from '../components/ChartsPanel.jsx'

const TABS = [
  { key: 'overview', label: '快速預覽' },
  { key: 'charts', label: '圖表分析' },
  { key: 'timeline', label: '時間軸' },
  { key: 'symptoms', label: '症狀分析' },
  { key: 'medications', label: '用藥' },
  { key: 'alerts', label: '警示' },
  { key: 'notes', label: '醫師備註' },
]

export default function PatientDetail() {
  const { id } = useParams()
  const [tab, setTab] = useState('overview')
  const [patient, setPatient] = useState(null)
  const [alerts, setAlerts] = useState([])
  const [notes, setNotes] = useState([])
  const [records, setRecords] = useState([])
  const [emotionTrend, setEmotionTrend] = useState([])
  const [medStats, setMedStats] = useState(null)
  const [medChanges, setMedChanges] = useState([])
  const [symptoms, setSymptoms] = useState([])
  const [loading, setLoading] = useState(true)
  const [err, setErr] = useState(null)

  const reload = async () => {
    setLoading(true)
    setErr(null)
    try {
      const [p, a, n, r, em, ms, mc, sy] = await Promise.all([
        fetchPatientById(id),
        apiGet('/alerts/', { patient_id: id }).catch(() => ({ alerts: [] })),
        apiGet('/doctor-notes/', { patient_id: id }).catch(() => ({ notes: [] })),
        apiGet(`/records/patient/${id}`).catch(() => ({ records: [] })),
        apiGet('/emotions/trend', { patient_id: id, days: 30 }).catch(() => ({ trend: [] })),
        apiGet('/medications/stats', { patient_id: id, days: 30 }).catch(() => null),
        apiGet('/medication-changes/', { patient_id: id }).catch(() => ({ changes: [] })),
        apiGet(`/symptoms/history/${id}`).catch(() => ({ history: [] })),
      ])
      setPatient(p)
      setAlerts(a.alerts ?? [])
      setNotes(n.notes ?? [])
      setRecords(r.records ?? [])
      setEmotionTrend(em.trend ?? [])
      setMedStats(ms)
      setMedChanges(mc.changes ?? [])
      setSymptoms(sy.history ?? [])
    } catch (e) {
      setErr(e.message)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    reload()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [id])

  const activeAlerts = useMemo(() => alerts.filter((x) => !x.resolved), [alerts])
  const prio = useMemo(() => patientPriority(activeAlerts), [activeAlerts])

  if (loading && !patient) {
    return (
      <>
        <h1 className="page-title">患者詳情</h1>
        <div className="placeholder">載入中…</div>
      </>
    )
  }
  if (err && !patient) {
    return (
      <>
        <h1 className="page-title">患者詳情</h1>
        <div className="error-bar">{err}</div>
        <Link to="/patients" className="row-link">← 返回患者清單</Link>
      </>
    )
  }
  if (!patient) return null

  return (
    <>
      <div className="page-head-row">
        <div>
          <h1 className="page-title">{patient.name}</h1>
          <p className="page-sub">
            {patient.age != null ? `${patient.age} 歲` : '年齡未填'} ·{' '}
            {patient.gender ?? '性別未填'} ·{' '}
            建檔 {fmtDate(patient.created_at)} ·{' '}
            ID {patient.id?.slice(0, 8)}
          </p>
        </div>
        <span className={`badge ${prio.badge}`}>{prio.label}</span>
      </div>

      <div className="profile-grid">
        <div className="card mini">
          <p className="card-title">未處理警示</p>
          <div className="card-value" style={{ color: activeAlerts.length ? 'var(--err)' : 'var(--text)' }}>
            {activeAlerts.length}
          </div>
        </div>
        <div className="card mini">
          <p className="card-title">服藥順從率（30天）</p>
          <div className="card-value">
            {medStats?.summary?.adherence_rate != null ? `${medStats.summary.adherence_rate}%` : '—'}
          </div>
        </div>
        <div className="card mini">
          <p className="card-title">就診紀錄</p>
          <div className="card-value">{records.length}</div>
        </div>
        <div className="card mini">
          <p className="card-title">醫師備註</p>
          <div className="card-value">{notes.length}</div>
        </div>
      </div>

      <div className="tabs">
        {TABS.map((t) => (
          <button
            key={t.key}
            className={`tab ${tab === t.key ? 'active' : ''}`}
            onClick={() => setTab(t.key)}
          >
            {t.label}
          </button>
        ))}
      </div>

      {err && <div className="error-bar">{err}</div>}

      {tab === 'overview' && (
        <OverviewPanel
          patient={patient}
          activeAlerts={activeAlerts}
          notes={notes}
          records={records}
          emotionTrend={emotionTrend}
          medStats={medStats}
        />
      )}
      {tab === 'charts' && (
        <ChartsPanel
          emotionTrend={emotionTrend}
          medStats={medStats}
          symptoms={symptoms}
          alerts={alerts}
          notes={notes}
          medChanges={medChanges}
        />
      )}
      {tab === 'timeline' && <TimelinePanel records={records} alerts={alerts} notes={notes} medChanges={medChanges} />}
      {tab === 'symptoms' && <SymptomsPanel symptoms={symptoms} />}
      {tab === 'medications' && <MedicationsPanel medStats={medStats} medChanges={medChanges} />}
      {tab === 'alerts' && <AlertsPanel alerts={alerts} onChanged={reload} />}
      {tab === 'notes' && <NotesPanel patientId={id} notes={notes} onChanged={reload} />}
    </>
  )
}

// ─── 快速預覽 ─────────────────────────────────────────────

function OverviewPanel({ patient, activeAlerts, notes, records, emotionTrend, medStats }) {
  const trendData = useMemo(() => {
    const byDay = new Map()
    for (const e of emotionTrend ?? []) {
      if (!e.date) continue
      const score = e.score ? e.score * 20 : null
      if (score == null) continue
      const cur = byDay.get(e.date) ?? { sum: 0, n: 0 }
      cur.sum += score
      cur.n += 1
      byDay.set(e.date, cur)
    }
    const emotionByDay = new Map()
    for (const [d, v] of byDay) emotionByDay.set(d, Math.round(v.sum / v.n))

    const adherenceByDay = new Map()
    for (const a of medStats?.adherence_trend ?? []) adherenceByDay.set(a.date, a.rate)

    const allDays = new Set([...emotionByDay.keys(), ...adherenceByDay.keys()])
    return [...allDays].sort().map((d) => {
      const md = new Date(d)
      return {
        date: `${md.getMonth() + 1}/${md.getDate()}`,
        emotion: emotionByDay.get(d) ?? null,
        adherence: adherenceByDay.get(d) ?? null,
      }
    })
  }, [emotionTrend, medStats])

  const lastNote = notes[0]
  const lastRecord = records[0]

  return (
    <div className="overview-grid">
      <div className="card">
        <h3 className="section-h">基本資料</h3>
        <dl className="kv">
          <dt>姓名</dt><dd>{patient.name}</dd>
          <dt>年齡</dt><dd>{patient.age ?? '—'}</dd>
          <dt>性別</dt><dd>{patient.gender ?? '—'}</dd>
          <dt>電話</dt><dd>{patient.phone ?? '—'}</dd>
          <dt>ICD-10</dt>
          <dd>{patient.icd10_codes?.length ? patient.icd10_codes.join(', ') : '—'}</dd>
        </dl>
      </div>

      <div className="card">
        <h3 className="section-h">最近狀態</h3>
        <ul className="bullet-list">
          <li>未處理警示：<strong style={{ color: activeAlerts.length ? 'var(--err)' : 'var(--ok)' }}>
            {activeAlerts.length}
          </strong></li>
          <li>最近回診：{lastRecord ? `${fmtDate(lastRecord.visit_date)} · ${lastRecord.diagnosis ?? '—'}` : '—'}</li>
          <li>最近備註：{lastNote ? `${relativeTime(lastNote.created_at)}` : '—'}</li>
          <li>30 天順從率：{medStats?.summary?.adherence_rate != null ? `${medStats.summary.adherence_rate}%` : '—'}</li>
        </ul>
      </div>

      <div className="card chart-card" style={{ gridColumn: '1 / -1' }}>
        <div className="chart-header">
          <div>
            <h2 className="chart-title">情緒 × 服藥順從率（30 天）</h2>
            <p className="chart-sub">情緒分數 0-100（=患者每日 1-5 評分 × 20）；順從率為當日打卡比例</p>
          </div>
        </div>
        {trendData.length > 0 ? (
          <TrendChart data={trendData} lines={['emotion', 'adherence']} height={280} />
        ) : (
          <div className="placeholder">尚無情緒或服藥日誌資料</div>
        )}
      </div>
    </div>
  )
}

// ─── 時間軸 ───────────────────────────────────────────────

function TimelinePanel({ records, alerts, notes, medChanges }) {
  const items = useMemo(() => {
    const list = []
    for (const r of records ?? []) {
      list.push({
        kind: 'record', ts: r.visit_date ?? r.created_at, key: `r-${r.id}`,
        title: r.diagnosis || '回診',
        body: r.prescription || r.notes || '',
        side: r.doctors?.name ? `醫師：${r.doctors.name}` : '',
      })
    }
    for (const a of alerts ?? []) {
      list.push({
        kind: 'alert', ts: a.created_at, key: `a-${a.id}`,
        title: a.title,
        body: a.detail || '',
        severity: a.severity,
        side: ALERT_TYPE_LABEL[a.alert_type] ?? a.alert_type,
      })
    }
    for (const n of notes ?? []) {
      list.push({
        kind: 'note', ts: n.created_at, key: `n-${n.id}`,
        title: '醫師備註',
        body: n.content,
        side: n.next_focus ? `下次重點：${n.next_focus}` : '',
      })
    }
    for (const m of medChanges ?? []) {
      const labels = {
        start: '新增藥物', stop: '停藥', dose_up: '加量', dose_down: '減量',
        switch: '換藥', frequency: '頻次調整', other: '調藥',
      }
      list.push({
        kind: 'medchange', ts: m.effective_date ?? m.created_at, key: `m-${m.id}`,
        title: labels[m.change_type] ?? m.change_type,
        body: [
          m.previous_dosage && `原 ${m.previous_dosage}`,
          m.new_dosage && `新 ${m.new_dosage}`,
          m.reason,
        ].filter(Boolean).join(' · '),
        side: '',
      })
    }
    list.sort((a, b) => new Date(b.ts ?? 0) - new Date(a.ts ?? 0))
    return list
  }, [records, alerts, notes, medChanges])

  if (items.length === 0) {
    return <div className="placeholder">尚無時間軸事件</div>
  }

  return (
    <div className="timeline">
      {items.map((it) => (
        <div key={it.key} className={`tl-row tl-${it.kind}`}>
          <div className="tl-time">{fmtDate(it.ts)}</div>
          <div className="tl-dot" />
          <div className="tl-body">
            <div className="tl-head">
              <span className="tl-kind">
                {it.kind === 'record' && '回診'}
                {it.kind === 'alert' && (
                  <span className={`badge ${SEVERITY_TO_BADGE[it.severity] ?? 'warn'}`}>
                    {SEVERITY_LABEL[it.severity] ?? it.severity}
                  </span>
                )}
                {it.kind === 'note' && '備註'}
                {it.kind === 'medchange' && '調藥'}
              </span>
              <strong>{it.title}</strong>
              {it.side && <span className="cell-dim">· {it.side}</span>}
            </div>
            {it.body && <p className="tl-text">{it.body}</p>}
          </div>
        </div>
      ))}
    </div>
  )
}

// ─── 用藥 ─────────────────────────────────────────────────

function MedicationsPanel({ medStats, medChanges }) {
  if (!medStats) {
    return <div className="placeholder">尚無藥物統計資料</div>
  }
  const meds = medStats.medications ?? []
  return (
    <>
      <div className="card">
        <h3 className="section-h">用藥清單（30 天）</h3>
        {meds.length === 0 ? (
          <p className="cell-dim">尚未建立任何藥物</p>
        ) : (
          <table className="data-table">
            <thead>
              <tr>
                <th>藥名</th>
                <th>劑量</th>
                <th>類別</th>
                <th style={{ width: 110 }}>順從率</th>
                <th style={{ width: 90 }}>療效</th>
                <th style={{ width: 90 }}>打卡數</th>
              </tr>
            </thead>
            <tbody>
              {meds.map((m) => (
                <tr key={m.id}>
                  <td className="cell-strong">{m.name}</td>
                  <td className="cell-dim">{m.dosage ?? '—'}</td>
                  <td className="cell-dim">{m.category ?? '—'}</td>
                  <td>{m.adherence_rate}%</td>
                  <td>{m.avg_effectiveness ?? '—'}</td>
                  <td className="cell-dim">{m.total_logs}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      <div className="card">
        <h3 className="section-h">調藥紀錄</h3>
        {medChanges.length === 0 ? (
          <p className="cell-dim">尚無調藥紀錄</p>
        ) : (
          <ul className="bullet-list">
            {medChanges.map((c) => (
              <li key={c.id}>
                <strong>{fmtDate(c.effective_date ?? c.created_at)}</strong> ·{' '}
                {c.change_type}
                {c.previous_dosage && ` · 原 ${c.previous_dosage}`}
                {c.new_dosage && ` → 新 ${c.new_dosage}`}
                {c.reason && <span className="cell-dim"> · {c.reason}</span>}
              </li>
            ))}
          </ul>
        )}
      </div>
    </>
  )
}

// ─── 症狀分析 ─────────────────────────────────────────────

function SymptomsPanel({ symptoms }) {
  if (!symptoms || symptoms.length === 0) {
    return <div className="placeholder">尚無症狀分析紀錄</div>
  }
  const sorted = [...symptoms].sort(
    (a, b) => new Date(b.created_at ?? 0) - new Date(a.created_at ?? 0),
  )
  return (
    <div className="symptom-list">
      {sorted.map((s) => {
        const ai = s.ai_response || {}
        const tags = Array.isArray(s.symptoms) ? s.symptoms : []
        const summary = ai.summary || ai.assessment || ai.advice || ''
        const possible = Array.isArray(ai.possible_conditions) ? ai.possible_conditions : []
        const urgency = ai.urgency || ai.triage_level
        const recommend = ai.recommendation || ai.suggestion
        return (
          <div key={s.id} className="card symptom-card">
            <div className="symptom-head">
              <span className="cell-dim">{fmtDate(s.created_at, true)} · {relativeTime(s.created_at)}</span>
              {urgency && <span className={`badge ${urgency === 'high' || urgency === 'critical' ? 'err' : urgency === 'low' ? 'ok' : 'warn'}`}>{urgency}</span>}
            </div>
            {tags.length > 0 && (
              <div className="symptom-tags">
                {tags.map((t, i) => (<span key={i} className="badge">{t}</span>))}
              </div>
            )}
            {summary && <p className="symptom-summary">{summary}</p>}
            {possible.length > 0 && (
              <div className="symptom-possible">
                <strong>可能狀況：</strong>
                <span className="cell-dim">{possible.map((c) => (typeof c === 'string' ? c : c?.name || c?.condition)).filter(Boolean).join('、')}</span>
              </div>
            )}
            {recommend && <p className="symptom-recommend"><strong>建議：</strong>{recommend}</p>}
          </div>
        )
      })}
    </div>
  )
}

// ─── 警示 ─────────────────────────────────────────────────

function AlertsPanel({ alerts, onChanged }) {
  const [busyId, setBusyId] = useState(null)
  const list = useMemo(
    () => [...alerts].sort((a, b) => new Date(b.created_at) - new Date(a.created_at)),
    [alerts],
  )
  const act = async (id, body) => {
    setBusyId(id)
    try {
      await apiPut(`/alerts/${id}`, body)
      await onChanged()
    } finally {
      setBusyId(null)
    }
  }
  if (list.length === 0) return <div className="placeholder">此患者目前沒有警示</div>
  return (
    <div className="alert-list">
      {list.map((a) => {
        const badge = SEVERITY_TO_BADGE[a.severity] ?? 'warn'
        return (
          <div key={a.id} className="alert-card">
            <div className="alert-card-head">
              <div>
                <span className={`badge ${badge}`}>{SEVERITY_LABEL[a.severity] ?? a.severity}</span>
                <span className="alert-type">{ALERT_TYPE_LABEL[a.alert_type] ?? a.alert_type}</span>
              </div>
              <div className="alert-meta">{fmtDate(a.created_at, true)}</div>
            </div>
            <h3 className="alert-title">{a.title}</h3>
            {a.detail && <p className="alert-detail">{a.detail}</p>}
            <div className="alert-foot">
              <div className="alert-patient">
                {a.acknowledged && <span className="cell-dim">已確認 · </span>}
                {a.resolved ? <span className="badge ok">已結案</span> : <span className="cell-dim">處理中</span>}
              </div>
              <div className="alert-actions">
                {!a.acknowledged && !a.resolved && (
                  <button className="btn" disabled={busyId === a.id}
                    onClick={() => act(a.id, { acknowledged: true, acknowledged_by: getActiveDoctorId() || undefined })}>
                    確認
                  </button>
                )}
                {!a.resolved && (
                  <button className="btn btn-primary" disabled={busyId === a.id}
                    onClick={() => act(a.id, { resolved: true })}>
                    結案
                  </button>
                )}
              </div>
            </div>
          </div>
        )
      })}
    </div>
  )
}

// ─── 醫師備註 ─────────────────────────────────────────────

function NotesPanel({ patientId, notes, onChanged }) {
  const [content, setContent] = useState('')
  const [nextFocus, setNextFocus] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const [err, setErr] = useState(null)
  const doctorId = getActiveDoctorId()

  const submit = async (e) => {
    e.preventDefault()
    if (!content.trim()) return
    setSubmitting(true)
    setErr(null)
    try {
      await apiPost('/doctor-notes/', {
        patient_id: patientId,
        doctor_id: doctorId || undefined,
        content: content.trim(),
        next_focus: nextFocus.trim() || undefined,
      })
      setContent('')
      setNextFocus('')
      await onChanged()
    } catch (e) {
      setErr(e.message)
    } finally {
      setSubmitting(false)
    }
  }

  const remove = async (id) => {
    if (!confirm('確定刪除這則備註？')) return
    try {
      await apiDelete(`/doctor-notes/${id}`)
      await onChanged()
    } catch (e) {
      setErr(e.message)
    }
  }

  return (
    <>
      <form className="card" onSubmit={submit}>
        <h3 className="section-h">新增備註</h3>
        {!doctorId && (
          <p className="cell-dim" style={{ marginTop: 0 }}>
            尚未在「設定」選擇醫師身份；備註會被建立但 doctor_id 為空。
          </p>
        )}
        <textarea
          className="text-input"
          rows={3}
          placeholder="這次回診觀察、處置、用藥反應…"
          value={content}
          onChange={(e) => setContent(e.target.value)}
        />
        <input
          className="text-input"
          style={{ marginTop: 8 }}
          placeholder="下次回診重點（選填）"
          value={nextFocus}
          onChange={(e) => setNextFocus(e.target.value)}
        />
        <div className="form-foot">
          {err && <span className="error-bar inline">{err}</span>}
          <button className="btn btn-primary" type="submit" disabled={submitting || !content.trim()}>
            {submitting ? '儲存中…' : '儲存備註'}
          </button>
        </div>
      </form>

      {notes.length === 0 ? (
        <div className="placeholder">尚無備註</div>
      ) : (
        <div className="note-list">
          {notes.map((n) => (
            <div key={n.id} className="note-card">
              <div className="note-head">
                <span className="cell-dim">{fmtDate(n.created_at, true)} · {relativeTime(n.created_at)}</span>
                <button className="btn btn-quiet" onClick={() => remove(n.id)}>刪除</button>
              </div>
              <p className="note-content">{n.content}</p>
              {n.next_focus && (
                <p className="note-focus"><strong>下次重點：</strong>{n.next_focus}</p>
              )}
            </div>
          ))}
        </div>
      )}
    </>
  )
}
