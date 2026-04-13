import { Routes, Route, NavLink, Navigate } from 'react-router-dom'
import Dashboard from './pages/Dashboard.jsx'
import PatientList from './pages/PatientList.jsx'
import PatientDetail from './pages/PatientDetail.jsx'
import Alerts from './pages/Alerts.jsx'
import Settings from './pages/Settings.jsx'

export default function App() {
  return (
    <div className="app">
      <header className="topbar">
        <div className="brand">
          <span className="brand-mark">MD</span>
          <span className="brand-name">Piece · 醫師端</span>
        </div>
        <nav className="nav">
          <NavLink to="/dashboard" className="nav-item">儀表板</NavLink>
          <NavLink to="/patients" className="nav-item">患者清單</NavLink>
          <NavLink to="/alerts" className="nav-item">警示</NavLink>
          <NavLink to="/settings" className="nav-item">設定</NavLink>
        </nav>
      </header>

      <main>
        <Routes>
          <Route path="/" element={<Navigate to="/dashboard" replace />} />
          <Route path="/dashboard" element={<Dashboard />} />
          <Route path="/patients" element={<PatientList />} />
          <Route path="/patients/:id" element={<PatientDetail />} />
          <Route path="/alerts" element={<Alerts />} />
          <Route path="/settings" element={<Settings />} />
        </Routes>
      </main>
    </div>
  )
}
