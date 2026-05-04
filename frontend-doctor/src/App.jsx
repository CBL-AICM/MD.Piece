import { useState } from 'react'
import { Routes, Route, NavLink, Navigate } from 'react-router-dom'
import Dashboard from './pages/Dashboard.jsx'
import PatientList from './pages/PatientList.jsx'
import PatientDetail from './pages/PatientDetail.jsx'
import Reports from './pages/Reports.jsx'
import Alerts from './pages/Alerts.jsx'
import Settings from './pages/Settings.jsx'
import Login from './pages/Login.jsx'
import { getCurrentUser, getDoctorProfile, logout as doLogout } from './lib/auth.js'

export default function App() {
  const [user, setUser] = useState(() => getCurrentUser())

  if (!user) {
    return <Login onAuthed={(u) => setUser(u)} />
  }

  const profile = getDoctorProfile() || {}
  const onLogout = () => {
    if (!confirm('確定要登出嗎？')) return
    doLogout()
    setUser(null)
  }

  return (
    <div className="app">
      <header className="topbar">
        <div className="brand">
          <span className="brand-mark">MD</span>
          <span className="brand-name">Piece</span>
          <span className="brand-sep">·</span>
          <span className="brand-name" style={{ color: 'var(--text-dim)', fontWeight: 500 }}>
            醫師端
          </span>
        </div>
        <nav className="nav">
          <NavLink to="/dashboard" className="nav-item">儀表板</NavLink>
          <NavLink to="/patients" className="nav-item">患者清單</NavLink>
          <NavLink to="/reports" className="nav-item">整合報告</NavLink>
          <NavLink to="/alerts" className="nav-item">警示</NavLink>
          <NavLink to="/settings" className="nav-item">設定</NavLink>
        </nav>
        <div className="topbar-user">
          <span className="topbar-user-name">
            {user.nickname || user.username}
            {profile.specialty && <span className="topbar-user-spec"> · {profile.specialty}</span>}
          </span>
          <button className="btn btn-quiet" onClick={onLogout} title="登出">登出</button>
        </div>
      </header>

      <main>
        <Routes>
          <Route path="/" element={<Navigate to="/dashboard" replace />} />
          <Route path="/dashboard" element={<Dashboard />} />
          <Route path="/patients" element={<PatientList />} />
          <Route path="/patients/:id" element={<PatientDetail />} />
          <Route path="/reports" element={<Reports />} />
          <Route path="/alerts" element={<Alerts />} />
          <Route path="/settings" element={<Settings />} />
        </Routes>
      </main>
    </div>
  )
}
