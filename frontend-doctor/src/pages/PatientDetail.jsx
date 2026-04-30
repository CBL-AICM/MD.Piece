import { useEffect, useState } from 'react'
import { useParams } from 'react-router-dom'
import { apiGet, apiPost } from '../lib/api.js'

const SIGNAL_COLOR = {
  red: 'var(--err)',
  yellow: 'var(--warn)',
  green: 'var(--ok)',
  gray: 'var(--text-dim)',
}

export default function PatientDetail() {
  const { id } = useParams()
  const [preview, setPreview] = useState(null)
  const [timeline, setTimeline] = useState(null)
  const [comparison, setComparison] = useState(null)
  const [labs, setLabs] = useState(null)
  const [eduDraft, setEduDraft] = useState(null)
  const [eduLoading, setEduLoading] = useState(false)
  const [error, setError] = useState(null)

  useEffect(() => {
    Promise.all([
      apiGet(`/doctor-dashboard/preview/${id}`),
      apiGet(`/timeline/${id}`),
      apiGet(`/timeline/${id}/compare`),
      apiGet(`/vitals/lab/${id}/translated`),
    ])
      .then(([p, t, c, l]) => {
        setPreview(p)
        setTimeline(t)
        setComparison(c)
        setLabs(l)
      })
      .catch((e) => setError(e.message))
  }, [id])

  async function genEducation() {
    setEduLoading(true)
    try {
      const draft = await apiPost('/education/personalized', {
        patient_id: id,
        auto_send: false,
      })
      setEduDraft(draft)
    } catch (e) {
      setEduDraft({ draft: `產生失敗：${e.message}` })
    } finally {
      setEduLoading(false)
    }
  }

  if (error) return <p style={{ color: 'var(--err)' }}>{error}</p>
  if (!preview) return <p>載入患者資料中…</p>

  return (
    <>
      <h1 className="page-title">{preview.patient_name || '患者'} 詳情</h1>
      <p className="page-sub">
        ID: {id} · {preview.age ?? '—'} 歲 ·{' '}
        <span style={{ color: SIGNAL_COLOR[preview.signal] }}>● {preview.priority}</span>
      </p>

      {/* 回診前快速預覽卡 */}
      <div className="card" style={{ marginBottom: 16 }}>
        <h2 className="chart-title">回診前快速預覽</h2>
        <ul style={{ paddingLeft: 18, lineHeight: 1.8 }}>
          {preview.highlights?.map((h, i) => (
            <li key={i}>{h}</li>
          ))}
        </ul>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 12, marginTop: 12 }}>
          <Stat label="服藥順從性" value={preview.adherence != null ? `${preview.adherence}%` : '—'} />
          <Stat label="平均情緒" value={preview.emotion_avg != null ? `${preview.emotion_avg}/5` : '—'} />
          <Stat label="連續低落天數" value={preview.emotion_consecutive_low_days || 0} />
        </div>
        {preview.last_note && (
          <div style={{ marginTop: 16, padding: 12, background: 'var(--bg-sunken)', borderRadius: 8 }}>
            <strong>上次備註提醒：</strong>
            <p style={{ marginTop: 6 }}>{preview.last_note.content}</p>
            {preview.last_note.next_focus && (
              <p style={{ marginTop: 6, color: 'var(--warn)' }}>
                下次觀察重點：{preview.last_note.next_focus}
              </p>
            )}
          </div>
        )}
      </div>

      {/* 跨回診比較 */}
      <div className="card" style={{ marginBottom: 16 }}>
        <h2 className="chart-title">跨回診比較</h2>
        {!comparison?.this_period ? (
          <p style={{ color: 'var(--text-faint)' }}>{comparison?.message || '尚無資料'}</p>
        ) : (
          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 14 }}>
            <thead>
              <tr style={{ color: 'var(--text-dim)' }}>
                <th style={{ textAlign: 'left', padding: 8 }}>指標</th>
                <th style={{ textAlign: 'right', padding: 8 }}>上期</th>
                <th style={{ textAlign: 'right', padding: 8 }}>本期</th>
                <th style={{ textAlign: 'right', padding: 8 }}>變化</th>
              </tr>
            </thead>
            <tbody>
              {[
                ['症狀嚴重度均值', 'severity_mean'],
                ['情緒均值', 'emotion_mean'],
                ['服藥率', 'adherence_rate'],
              ].map(([label, key]) => (
                <tr key={key} style={{ borderTop: '1px solid var(--border)' }}>
                  <td style={{ padding: 8 }}>{label}</td>
                  <td style={{ padding: 8, textAlign: 'right' }}>
                    {comparison.last_period?.[key] ?? '—'}
                  </td>
                  <td style={{ padding: 8, textAlign: 'right' }}>
                    {comparison.this_period?.[key] ?? '—'}
                  </td>
                  <td style={{ padding: 8, textAlign: 'right' }}>
                    {formatDelta(comparison.deltas?.[key])}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      {/* 治療時間軸 */}
      <div className="card" style={{ marginBottom: 16 }}>
        <h2 className="chart-title">治療時間軸</h2>
        {!timeline?.events?.length ? (
          <p style={{ color: 'var(--text-faint)' }}>近期無事件</p>
        ) : (
          <ul style={{ paddingLeft: 0, listStyle: 'none' }}>
            {timeline.events.slice(0, 12).map((e, i) => (
              <li
                key={i}
                style={{ borderLeft: '2px solid var(--border)', paddingLeft: 12, marginLeft: 4, marginBottom: 12 }}
              >
                <div style={{ fontSize: 12, color: 'var(--text-dim)' }}>
                  {e.date} · {e.type}
                </div>
                <div style={{ fontWeight: 600 }}>{e.title}</div>
                {e.detail && <div style={{ color: 'var(--text-dim)', fontSize: 13 }}>{e.detail}</div>}
              </li>
            ))}
          </ul>
        )}
      </div>

      {/* 患者端白話檢驗 */}
      <div className="card" style={{ marginBottom: 16 }}>
        <h2 className="chart-title">患者端白話檢驗（可推送預覽）</h2>
        {!labs?.translated?.length ? (
          <p style={{ color: 'var(--text-faint)' }}>尚未上傳檢驗數值</p>
        ) : (
          labs.translated.map((t) => (
            <div key={t.code} style={{ padding: '8px 0', borderBottom: '1px solid var(--border)' }}>
              <strong>{t.casual_name}</strong>
              <span style={{ marginLeft: 8, fontSize: 12, color: 'var(--text-dim)' }}>
                等級 {t.level} {t.trend ? `· 趨勢 ${t.trend}` : ''}
              </span>
              <p style={{ marginTop: 4 }}>{t.message}</p>
            </div>
          ))
        )}
      </div>

      {/* 個人化衛教生成 */}
      <div className="card">
        <h2 className="chart-title">個人化衛教（醫師審核）</h2>
        <button onClick={genEducation} disabled={eduLoading} className="btn-primary">
          {eduLoading ? '產生中…' : '依最新備註與數據產生草稿'}
        </button>
        {eduDraft && (
          <div style={{ marginTop: 12, whiteSpace: 'pre-wrap', lineHeight: 1.7 }}>
            {eduDraft.draft}
          </div>
        )}
      </div>
    </>
  )
}

function Stat({ label, value }) {
  return (
    <div style={{ background: 'var(--bg-sunken)', padding: 10, borderRadius: 8 }}>
      <div style={{ fontSize: 12, color: 'var(--text-dim)' }}>{label}</div>
      <div style={{ fontSize: 18, fontWeight: 700 }}>{value}</div>
    </div>
  )
}

function formatDelta(d) {
  if (d == null) return '—'
  const sign = d > 0 ? '+' : ''
  const color = d > 0 ? 'var(--err)' : d < 0 ? 'var(--ok)' : 'var(--text-dim)'
  return <span style={{ color }}>{sign}{d}</span>
}
