import { Routes, Route, NavLink, Navigate, useLocation, useNavigate } from 'react-router-dom'
import Dashboard from './pages/Dashboard.jsx'
import PatientList from './pages/PatientList.jsx'
import PatientDetail from './pages/PatientDetail.jsx'
import Reports from './pages/Reports.jsx'
import Alerts from './pages/Alerts.jsx'
import Settings from './pages/Settings.jsx'
import Login from './pages/Login.jsx'
import Register from './pages/Register.jsx'
import { clearSession, getUser, isAuthenticated } from './lib/auth.js'

function RequireAuth({ children }) {
  const location = useLocation()
  if (!isAuthenticated()) {
    return <Navigate to="/login" state={{ from: location }} replace />
  }
  return children
}

function Shell({ children }) {
  const navigate = useNavigate()
  const user = getUser()
  const onLogout = () => {
    clearSession()
    navigate('/login', { replace: true })
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
          {user && <span className="cell-dim">{user.nickname || user.username}</span>}
          <button type="button" className="btn btn-ghost" onClick={onLogout}>登出</button>
        </div>
      </header>

      <main>{children}</main>
    </div>
  )
}

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<Login />} />
      <Route path="/register" element={<Register />} />
      <Route
        path="/*"
        element={
          <RequireAuth>
            <Shell>
              <Routes>
                <Route path="/" element={<Navigate to="/dashboard" replace />} />
                <Route path="/dashboard" element={<Dashboard />} />
                <Route path="/patients" element={<PatientList />} />
                <Route path="/patients/:id" element={<PatientDetail />} />
                <Route path="/reports" element={<Reports />} />
                <Route path="/alerts" element={<Alerts />} />
                <Route path="/settings" element={<Settings />} />
              </Routes>
            </Shell>
          </RequireAuth>
        }
      />
    </Routes>
  )
}
