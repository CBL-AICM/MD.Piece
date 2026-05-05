import { useState } from 'react'
import { loginDoctor, registerDoctor } from '../lib/auth.js'

const SPECIALTIES = [
  '家醫科', '內科', '外科', '小兒科', '婦產科', '精神科',
  '神經內科', '神經外科', '骨科',
  '心臟內科', '腸胃內科', '腎臟內科', '胸腔內科', '內分泌新陳代謝科',
  '風濕免疫科', '過敏免疫風濕科',
  '感染科', '血液腫瘤科', '皮膚科', '眼科', '耳鼻喉科', '泌尿科',
  '復健科', '放射科', '麻醉科', '急診醫學科',
  '中醫科', '牙科', '病理科', '核子醫學科',
  '其他',
]

export default function Login({ onAuthed }) {
  const [tab, setTab] = useState('login')

  return (
    <div className="auth-shell">
      <div className="auth-card">
        <header className="auth-header">
          <div className="brand" style={{ justifyContent: 'center' }}>
            <span className="brand-mark">MD</span>
            <span className="brand-name">Piece · 醫師端</span>
          </div>
          <p className="auth-sub">以醫師身份登入後，可檢視患者推送的紀錄並產生回診報告。</p>
        </header>

        <div className="auth-tabs">
          <button
            className={`auth-tab ${tab === 'login' ? 'active' : ''}`}
            onClick={() => setTab('login')}
          >
            登入
          </button>
          <button
            className={`auth-tab ${tab === 'register' ? 'active' : ''}`}
            onClick={() => setTab('register')}
          >
            註冊
          </button>
        </div>

        {tab === 'login' ? <LoginForm onAuthed={onAuthed} /> : <RegisterForm onAuthed={onAuthed} />}

        <p className="auth-foot">
          MD.Piece 為 AI 輔助工具，僅供醫病溝通與資料整理；不可作為診斷或醫療依據。
        </p>
      </div>
    </div>
  )
}

function LoginForm({ onAuthed }) {
  const [form, setForm] = useState({ username: '', password: '', doctor_key: '' })
  const [err, setErr] = useState(null)
  const [busy, setBusy] = useState(false)

  const submit = async (e) => {
    e.preventDefault()
    setErr(null)
    setBusy(true)
    try {
      const u = await loginDoctor(form)
      onAuthed?.(u)
    } catch (e) {
      setErr(e.message)
    } finally {
      setBusy(false)
    }
  }

  const set = (k) => (e) => setForm((f) => ({ ...f, [k]: e.target.value }))

  return (
    <form className="auth-form" onSubmit={submit}>
      <Field label="帳號">
        <input className="text-input" required value={form.username}
          onChange={set('username')} placeholder="3-32 字元" />
      </Field>
      <Field label="密碼">
        <input className="text-input" type="password" required value={form.password}
          onChange={set('password')} placeholder="至少 6 個字元" />
      </Field>
      <Field label="醫師通行碼">
        <input className="text-input" type="password" required value={form.doctor_key}
          onChange={set('doctor_key')} placeholder="僅醫師持有的通行碼" />
      </Field>
      {err && <div className="error-bar inline">{err}</div>}
      <button className="btn btn-primary auth-submit" disabled={busy}>
        {busy ? '登入中…' : '登入醫師端'}
      </button>
    </form>
  )
}

function RegisterForm({ onAuthed }) {
  const [step, setStep] = useState(1)
  const [form, setForm] = useState({
    nickname: '', username: '', password: '', password2: '',
    doctor_key: '',
    specialty: '家醫科', gender: '', birthday: '', phone: '',
  })
  const [err, setErr] = useState(null)
  const [busy, setBusy] = useState(false)

  const set = (k) => (e) => setForm((f) => ({ ...f, [k]: e.target.value }))

  const goNext = (e) => {
    e.preventDefault()
    setErr(null)
    if (!/^[A-Za-z0-9_.\-]{3,32}$/.test(form.username)) {
      setErr('帳號限英數字 _ . -，3-32 字元')
      return
    }
    if (form.password.length < 6) {
      setErr('密碼至少 6 個字元')
      return
    }
    if (form.password !== form.password2) {
      setErr('兩次輸入的密碼不一致')
      return
    }
    if (!form.doctor_key.trim()) {
      setErr('請輸入醫師通行碼')
      return
    }
    setStep(2)
  }

  const submit = async (e) => {
    e.preventDefault()
    setErr(null)
    if (!form.nickname.trim()) {
      setErr('請輸入姓名 / 暱稱')
      return
    }
    setBusy(true)
    try {
      const u = await registerDoctor(form)
      onAuthed?.(u)
    } catch (e) {
      setErr(e.message)
    } finally {
      setBusy(false)
    }
  }

  if (step === 1) {
    return (
      <form className="auth-form" onSubmit={goNext}>
        <p className="auth-step-hint">步驟 1 / 2 · 帳號設定</p>
        <Field label="帳號">
          <input className="text-input" required value={form.username}
            onChange={set('username')} placeholder="英數字 _ . - 共 3-32 字元"
            pattern="[A-Za-z0-9_.\-]{3,32}" autoFocus />
        </Field>
        <div className="auth-row">
          <Field label="密碼">
            <input className="text-input" type="password" required minLength={6} value={form.password}
              onChange={set('password')} placeholder="至少 6 字元" />
          </Field>
          <Field label="確認密碼">
            <input className="text-input" type="password" required minLength={6} value={form.password2}
              onChange={set('password2')} placeholder="再次輸入密碼" />
          </Field>
        </div>
        <Field label="醫師通行碼">
          <input className="text-input" type="password" required value={form.doctor_key}
            onChange={set('doctor_key')} placeholder="醫師專屬通行碼" />
        </Field>
        {err && <div className="error-bar inline">{err}</div>}
        <button className="btn btn-primary auth-submit" type="submit">
          下一步：填寫基本資料
        </button>
      </form>
    )
  }

  return (
    <form className="auth-form" onSubmit={submit}>
      <p className="auth-step-hint">步驟 2 / 2 · 基本資料</p>
      <Field label="姓名 / 暱稱">
        <input className="text-input" required maxLength={30} value={form.nickname}
          onChange={set('nickname')} placeholder="顯示在介面上的醫師姓名" autoFocus />
      </Field>
      <Field label="科別">
        <select className="text-input" value={form.specialty} onChange={set('specialty')}>
          {SPECIALTIES.map((s) => <option key={s} value={s}>{s}</option>)}
        </select>
      </Field>
      <div className="auth-row">
        <Field label="性別">
          <select className="text-input" value={form.gender} onChange={set('gender')}>
            <option value="">— 不填 —</option>
            <option value="male">男</option>
            <option value="female">女</option>
            <option value="other">其他</option>
          </select>
        </Field>
        <Field label="生日">
          <input className="text-input" type="date" value={form.birthday}
            onChange={set('birthday')} />
        </Field>
      </div>
      <Field label="聯絡電話（選填）">
        <input className="text-input" value={form.phone} onChange={set('phone')}
          placeholder="例如 02-1234-5678" />
      </Field>
      {err && <div className="error-bar inline">{err}</div>}
      <div className="auth-row">
        <button type="button" className="btn btn-quiet auth-submit"
          onClick={() => { setErr(null); setStep(1) }} disabled={busy}>
          上一步
        </button>
        <button className="btn btn-primary auth-submit" type="submit" disabled={busy}>
          {busy ? '建立中…' : '建立醫師帳號'}
        </button>
      </div>
    </form>
  )
}

function Field({ label, children }) {
  return (
    <label className="auth-field">
      <span className="auth-label">{label}</span>
      {children}
    </label>
  )
}
