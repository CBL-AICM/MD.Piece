import { useEffect, useState } from 'react'
import {
  apiGet, getApiBase, setApiBase,
  getActiveDoctorId, setActiveDoctorId,
} from '../lib/api.js'
import { getCurrentUser, getDoctorProfile } from '../lib/auth.js'

export default function Settings() {
  const [apiUrl, setApiUrl] = useState(() => getApiBase())
  const [doctorId, setDoctorId] = useState(() => getActiveDoctorId() ?? '')
  const [doctors, setDoctors] = useState([])
  const [test, setTest] = useState({ status: '', ok: null })
  const [savedAt, setSavedAt] = useState(null)
  const [err, setErr] = useState(null)
  const me = getCurrentUser() || {}
  const profile = getDoctorProfile() || {}

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

  useEffect(() => { queueMicrotask(loadDoctors) }, [])

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
      <p className="page-sub">您目前以醫師身份登入；後端位址、臨床醫師檔可在這裡調整。</p>

      {err && <div className="error-bar">{err}</div>}

      <div className="card">
        <h3 className="section-h">當前登入</h3>
        <dl className="kv">
          <dt>姓名</dt><dd>{me.nickname || '—'}</dd>
          <dt>帳號</dt><dd>{me.username ? `@${me.username}` : '—'}</dd>
          <dt>科別</dt><dd>{profile.specialty || '—'}</dd>
          <dt>性別</dt><dd>{({ male: '男', female: '女', other: '其他' })[profile.gender] || '—'}</dd>
          <dt>生日</dt><dd>{profile.birthday || '—'}</dd>
          <dt>聯絡電話</dt><dd>{profile.phone || '—'}</dd>
          <dt>使用者 ID</dt><dd><code>{me.id}</code></dd>
        </dl>
        <p className="cell-dim" style={{ fontSize: 12, marginTop: 12 }}>
          要修改個人資料請登出後重新註冊；性別 / 生日存於本機 localStorage。
        </p>
      </div>

      <form className="card" onSubmit={saveApi}>
        <h3 className="section-h">後端 API</h3>
        <p className="cell-dim" style={{ margin: '0 0 12px' }}>
          預設透過 Vite proxy 走 <code>/api</code>（同機後端 :8000）。需要連到不同主機時可填完整網址。
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

      <details className="card">
        <summary style={{ cursor: 'pointer', fontWeight: 600, color: 'var(--text)' }}>
          進階：手動指定臨床醫師檔（doctors 表）
        </summary>
        <p className="cell-dim" style={{ margin: '12px 0' }}>
          註冊時已自動建立並綁定一筆臨床醫師檔。一般情況不需動。
          只有在多個 doctor 紀錄需要切換時才用得到。
        </p>
        {doctors.length === 0 ? (
          <p className="cell-dim">後端尚無醫師資料。</p>
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
      </details>

      <div className="card">
        <h3 className="section-h">關於本介面</h3>
        <ul className="bullet-list">
          <li>連動同一個 FastAPI 後端，與患者端 PWA 共用 Supabase 資料庫</li>
          <li>患者每日情緒、服藥打卡、症狀分析、診前推送都會即時反映在患者詳情頁</li>
          <li>警示自動觸發：連續低落情緒 ≥ 3 天 → low_mood；7 天服藥率 &lt; 50% → missed_medication</li>
          <li>API 寫入 doctor_notes 已加 X-User-Id 角色檢查（醫師寫備註、患者寫 patient_push）</li>
        </ul>
      </div>
    </>
  )
}
