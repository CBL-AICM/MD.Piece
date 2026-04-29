import { useEffect, useState } from 'react'
import {
  apiGet, getApiBase, setApiBase,
  getActiveDoctorId, setActiveDoctorId,
} from '../lib/api.js'

export default function Settings() {
  const [apiUrl, setApiUrl] = useState(() => getApiBase())
  const [doctorId, setDoctorId] = useState(() => getActiveDoctorId() ?? '')
  const [doctors, setDoctors] = useState([])
  const [test, setTest] = useState({ status: '', ok: null })
  const [savedAt, setSavedAt] = useState(null)
  const [err, setErr] = useState(null)

  const loadDoctors = async () => {
    try {
      const r = await apiGet('/doctors/')
      setDoctors(r.doctors ?? [])
      setTest({ status: `已連線 · 醫師 ${r.doctors?.length ?? 0} 位`, ok: true })
      setErr(null)
    } catch (e) {
      setErr(e.message)
      setTest({ status: `離線：${e.message}`, ok: false })
    }
  }

  useEffect(() => {
    queueMicrotask(loadDoctors)
  }, [])

  const saveApi = (e) => {
    e.preventDefault()
    setApiBase(apiUrl.trim() || null)
    setSavedAt(Date.now())
    loadDoctors()
  }

  const saveDoctor = () => {
    setActiveDoctorId(doctorId || null)
    setSavedAt(Date.now())
  }

  return (
    <>
      <h1 className="page-title">設定</h1>
      <p className="page-sub">後端位址與醫師身份儲存於本機 localStorage</p>

      {err && <div className="error-bar">{err}</div>}

      <form className="card" onSubmit={saveApi}>
        <h3 className="section-h">後端 API</h3>
        <p className="cell-dim" style={{ margin: '0 0 12px' }}>
          預設透過 Vite proxy 走 <code>/api</code>（同機後端 :8000）。需要連到不同主機時可填完整網址，例如
          <code> http://192.168.1.10:8000</code>。
        </p>
        <input
          className="text-input"
          placeholder="/api 或 http://host:8000"
          value={apiUrl}
          onChange={(e) => setApiUrl(e.target.value)}
        />
        <div className="form-foot">
          <span className={`badge ${test.ok === true ? 'ok' : test.ok === false ? 'err' : ''}`}>
            {test.status || '未測試'}
          </span>
          <button className="btn btn-primary" type="submit">儲存並測試</button>
        </div>
      </form>

      <div className="card">
        <h3 className="section-h">醫師身份</h3>
        <p className="cell-dim" style={{ margin: '0 0 12px' }}>
          建立的備註與確認警示時，會帶上這位醫師的 ID。
        </p>
        {doctors.length === 0 ? (
          <p className="cell-dim">後端尚無醫師資料；請先以 API 建立。</p>
        ) : (
          <select
            className="text-input"
            value={doctorId}
            onChange={(e) => setDoctorId(e.target.value)}
          >
            <option value="">— 不指定 —</option>
            {doctors.map((d) => (
              <option key={d.id} value={d.id}>
                {d.name} · {d.specialty}
              </option>
            ))}
          </select>
        )}
        <div className="form-foot">
          {savedAt && <span className="cell-dim">已儲存</span>}
          <button className="btn btn-primary" onClick={saveDoctor} disabled={doctors.length === 0}>
            儲存
          </button>
        </div>
      </div>

      <div className="card">
        <h3 className="section-h">關於本介面</h3>
        <ul className="bullet-list">
          <li>連動同一個 FastAPI 後端，與患者端 PWA 共用 Supabase 資料庫</li>
          <li>患者每日情緒、服藥打卡、症狀分析都會即時反映在患者詳情頁</li>
          <li>警示系統來源：後端依規則寫入 <code>alerts</code> 表（亦可由其他子系統 POST）</li>
        </ul>
      </div>
    </>
  )
}
