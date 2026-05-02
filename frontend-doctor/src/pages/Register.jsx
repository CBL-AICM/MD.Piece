import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { apiPost } from '../lib/api.js'
import { setSession } from '../lib/auth.js'

export default function Register() {
  const [form, setForm] = useState({
    username: '',
    password: '',
    confirmPassword: '',
    nickname: '',
  })
  const [busy, setBusy] = useState(false)
  const [err, setErr] = useState(null)
  const navigate = useNavigate()

  const update = (k) => (e) => setForm((s) => ({ ...s, [k]: e.target.value }))

  const submit = async (e) => {
    e.preventDefault()
    if (!form.username || !form.password || !form.nickname) {
      setErr('請填寫帳號、密碼、顯示名稱')
      return
    }
    if (form.password.length < 6) {
      setErr('密碼至少 6 碼')
      return
    }
    if (form.password !== form.confirmPassword) {
      setErr('兩次密碼不一致')
      return
    }
    setBusy(true)
    setErr(null)
    try {
      const r = await apiPost('/auth/register', {
        username: form.username,
        password: form.password,
        nickname: form.nickname,
        role: 'doctor',
      })
      setSession(r.access_token, r.user)
      navigate('/dashboard', { replace: true })
    } catch (e) {
      setErr(e.message)
      setBusy(false)
    }
  }

  return (
    <div className="auth-wrap">
      <div className="card auth-card">
        <h1 className="page-title" style={{ marginTop: 0 }}>註冊新醫師</h1>
        <p className="page-sub">建立屬於你的 MD.Piece 醫師帳號</p>

        {err && <div className="error-bar">{err}</div>}

        <form onSubmit={submit} className="auth-form">
          <label className="auth-label">
            <span>帳號（英數）</span>
            <input
              className="text-input"
              type="text"
              autoComplete="username"
              value={form.username}
              onChange={update('username')}
              autoFocus
            />
          </label>
          <label className="auth-label">
            <span>顯示名稱</span>
            <input
              className="text-input"
              type="text"
              value={form.nickname}
              onChange={update('nickname')}
              placeholder="例：王醫師"
            />
          </label>
          <label className="auth-label">
            <span>密碼（至少 6 碼）</span>
            <input
              className="text-input"
              type="password"
              autoComplete="new-password"
              value={form.password}
              onChange={update('password')}
            />
          </label>
          <label className="auth-label">
            <span>確認密碼</span>
            <input
              className="text-input"
              type="password"
              autoComplete="new-password"
              value={form.confirmPassword}
              onChange={update('confirmPassword')}
            />
          </label>
          <button className="btn btn-primary" type="submit" disabled={busy}>
            {busy ? '註冊中…' : '建立帳號'}
          </button>
        </form>

        <div className="auth-footer">
          <span className="cell-dim">已經有帳號了？</span>
          <Link to="/login">回登入</Link>
        </div>
      </div>
    </div>
  )
}
