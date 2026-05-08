import { useEffect, useMemo, useState } from 'react'
import { apiGet } from '../lib/api.js'
import { fetchAllPatients } from '../lib/patients.js'
import { renderMarkdown } from '../lib/markdown.js'
import TrendChart from '../components/TrendChart.jsx'

// 固定免責聲明（PDF 結尾必印，不交給 LLM 生成）
const DOCTOR_PDF_DISCLAIMER_HTML =
  '<p><strong>⚠ 本報告內容為患者自行記錄之主觀紀錄整理</strong>，由 MD.Piece AI 彙整患者於應用程式中自填的症狀、情緒、用藥、飲食、就診等紀錄產生，<strong>未經臨床檢查或醫療專業驗證</strong>。</p>' +
  '<p>本報告僅供問診溝通參考，<strong>不構成醫療診斷、治療建議或處方依據</strong>。資料可能存在主觀偏差、記憶誤差或記錄遺漏，最終臨床判斷請以主治醫師親自評估為準。</p>'

function escapeHtml(s) {
  return String(s ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]))
}

function buildDoctorPDFHtml(report, patient) {
  const dateStr = new Date().toLocaleDateString('zh-TW', { year: 'numeric', month: 'long', day: 'numeric' })
  const reportBody = renderMarkdown(report?.report || '（暫無報告）')
  const counts = report?.raw_data || {}
  const periodLabel = report?.period_label || '近 30 天'
  const patientLine = patient ? `${escapeHtml(patient.name)}${patient.age != null ? `（${patient.age} 歲）` : ''}` : '—'

  const statsHtml =
    '<table class="stats"><tr>' +
    `<td><strong>${counts.symptom_count || 0}</strong><span>症狀紀錄</span></td>` +
    `<td><strong>${counts.emotion_count || 0}</strong><span>情緒紀錄</span></td>` +
    `<td><strong>${counts.medication_count || 0}</strong><span>用藥</span></td>` +
    `<td><strong>${counts.visit_count || 0}</strong><span>就診</span></td>` +
    '</tr></table>'

  return (
    '<!doctype html><html lang="zh-Hant"><head><meta charset="utf-8">' +
    `<title>MD.Piece 診前報告（醫師版）${dateStr}</title>` +
    '<style>' +
    '  @page { size: A4; margin: 18mm 16mm; }' +
    '  body { font-family: "Noto Sans TC","PingFang TC","Microsoft JhengHei",sans-serif; color:#222; line-height:1.75; font-size:14px; }' +
    '  h1 { font-size: 22px; margin: 0 0 4px; }' +
    '  .meta { color:#666; font-size:12px; margin-bottom:18px; }' +
    '  h2 { font-size:15px; margin:22px 0 8px; padding-bottom:4px; border-bottom:1px solid #ddd; color:#2a5d8f; }' +
    '  h3 { font-size:14px; margin:16px 0 6px; color:#2a5d8f; }' +
    '  p { margin:0 0 10px; }' +
    '  ul, ol { padding-left:22px; margin:0 0 10px; }' +
    '  ul li, ol li { margin-bottom:6px; }' +
    '  table.stats { width:100%; border-collapse:collapse; margin:6px 0 4px; }' +
    '  table.stats td { width:25%; text-align:center; padding:8px 4px; border:1px solid #e2e2e2; background:#f7f9fc; }' +
    '  table.stats td strong { display:block; font-size:18px; color:#2a5d8f; }' +
    '  table.stats td span { font-size:11px; color:#666; }' +
    '  .disclaimer { margin-top:28px; padding:12px 14px; border-top:2px solid #d9d9d9; background:#fafafa; font-size:11.5px; color:#555; line-height:1.6; }' +
    '  .disclaimer p { margin:0 0 6px; }' +
    '  .disclaimer p:last-child { margin:0; }' +
    '</style></head><body>' +
    '<h1>診前報告（醫師版）</h1>' +
    `<div class="meta">產出日期：${dateStr} · 患者：${patientLine} · 報告期間：${escapeHtml(periodLabel)}</div>` +
    '<h2>本期間紀錄概覽</h2>' +
    statsHtml +
    '<h2>整合摘要</h2>' +
    reportBody +
    '<div class="disclaimer">' +
    DOCTOR_PDF_DISCLAIMER_HTML +
    '</div>' +
    '</body></html>'
  )
}

function downloadDoctorPDF(report, patient) {
  if (!report) return
  const html = buildDoctorPDFHtml(report, patient)
  const w = window.open('', '_blank')
  if (!w) {
    alert('瀏覽器擋掉了新視窗，請允許彈出視窗後再試')
    return
  }
  w.document.open()
  w.document.write(html)
  w.document.close()
  w.onload = () => setTimeout(() => { try { w.focus(); w.print() } catch (_) {} }, 250)
}

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
  const [report, setReport] = useState(null)
  const [reportLoading, setReportLoading] = useState(false)
  const [reportErr, setReportErr] = useState(null)

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
    // 切換患者就清掉舊報告
    setReport(null)
    setReportErr(null)
  }, [patientId, days])

  const generateReport = async () => {
    if (!patientId) return
    setReportLoading(true)
    setReportErr(null)
    try {
      const r = await apiGet(`/reports/${patientId}/monthly`)
      setReport(r)
    } catch (e) {
      setReportErr(e.message)
    } finally {
      setReportLoading(false)
    }
  }

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

      {/* MD.Piece 回診報告 */}
      <div className="card report-card" style={{ marginBottom: 16 }}>
        <div className="report-head">
          <div>
            <h2 className="section-h" style={{ margin: 0 }}>MD.Piece 回診報告</h2>
            <p className="cell-dim" style={{ margin: '6px 0 0', fontSize: 13 }}>
              整合患者上次回診以來的症狀／情緒／用藥／就診／飲食紀錄，由 Claude 產出專業摘要供醫師參考。
            </p>
          </div>
          <div style={{ display: 'flex', gap: 8 }}>
            <button
              className="btn btn-primary"
              onClick={generateReport}
              disabled={!patientId || reportLoading}
            >
              {reportLoading ? '產生中…' : (report ? '重新產生' : '產生報告')}
            </button>
            {report && (
              <button
                className="btn btn-ghost"
                onClick={() => downloadDoctorPDF(report, selected)}
                title="下載醫師版 PDF（會開啟列印視窗，請選擇「另存為 PDF」）"
              >
                下載 PDF
              </button>
            )}
          </div>
        </div>
        {reportErr && <div className="error-bar inline" style={{ marginTop: 12 }}>{reportErr}</div>}
        {report && (
          <>
            <div
              className="report-body"
              dangerouslySetInnerHTML={{ __html: renderMarkdown(report.report) }}
            />
            <div className="report-meta">
              <span>產生時間：{new Date(report.generated_at).toLocaleString('zh-TW')}</span>
              <span>· 來源：{report.source === 'ai' ? 'MD.Piece' : '原始摘要'}</span>
              {report.period_label && <span>· 期間：{report.period_label}</span>}
              {report.raw_data && (
                <span>· 樣本：症狀 {report.raw_data.symptom_count} / 情緒 {report.raw_data.emotion_count} / 用藥 {report.raw_data.medication_count} / 就診 {report.raw_data.visit_count}</span>
              )}
            </div>
            <div className="disclaimer">
              ⚠ <strong>本報告內容為患者自行記錄之主觀紀錄整理</strong>，由 MD.Piece AI 彙整患者於應用程式中自填的症狀、情緒、用藥、飲食、就診等紀錄產生，<strong>未經臨床檢查或醫療專業驗證</strong>。
              本報告僅供問診溝通參考，<strong>不構成醫療診斷、治療建議或處方依據</strong>。資料可能存在主觀偏差、記憶誤差或記錄遺漏，最終臨床判斷請以主治醫師親自評估為準。
            </div>
          </>
        )}
        {!report && !reportLoading && (
          <p className="cell-dim" style={{ margin: '12px 0 0' }}>
            選好患者後點「產生報告」即可。
          </p>
        )}
      </div>

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
