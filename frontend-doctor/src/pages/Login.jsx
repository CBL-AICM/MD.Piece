import { useState } from 'react'
import { Link, useNavigate, useLocation } from 'react-router-dom'
import { apiPost } from '../lib/api.js'
import { setSession } from '../lib/auth.js'

export default function Login() {
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [busy, setBusy] = useState(false)
  const [err, setErr] = useState(null)
  const navigate = useNavigate()
  const location = useLocation()
  const from = location.state?.from?.pathname || '/dashboard'

  const submit = async (e) => {
    e.preventDefault()
    if (!username || !password) {
      setErr('請輸入帳號與密碼')
      return
    }
    setBusy(true)
    setErr(null)
    try {
      const r = await apiPost('/auth/login', { username, password })
      if (r?.user?.role !== 'doctor') {
        setErr('此帳號非醫師身份，無法登入醫師端')
        setBusy(false)
        return
      }
      setSession(r.access_token, r.user)
      navigate(from, { replace: true })
    } catch (e) {
      setErr(e.message)
      setBusy(false)
    }
  }

  return (
    <div className="auth-wrap">
      <div className="card auth-card">
        <h1 className="page-title" style={{ marginTop: 0 }}>醫師登入</h1>
        <p className="page-sub">MD.Piece · 醫師端</p>

        {err && <div className="error-bar">{err}</div>}

        <form onSubmit={submit} className="auth-form">
          <label className="auth-label">
            <span>帳號</span>
            <input
              className="text-input"
              type="text"
              autoComplete="username"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              autoFocus
            />
          </label>
          <label className="auth-label">
            <span>密碼</span>
            <input
              className="text-input"
              type="password"
              autoComplete="current-password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
            />
          </label>
          <button className="btn btn-primary" type="submit" disabled={busy}>
            {busy ? '登入中…' : '登入'}
          </button>
        </form>

        <div className="auth-footer">
          <span className="cell-dim">還沒有帳號？</span>
          <Link to="/register">註冊新醫師</Link>
        </div>
      </div>
    </div>
  )
}
