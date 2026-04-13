import { useEffect, useState } from 'react'
import { apiGet } from '../lib/api.js'

export default function Dashboard() {
  const [status, setStatus] = useState('檢查後端連線中…')
  const [statusOk, setStatusOk] = useState(null)

  useEffect(() => {
    apiGet('/doctors/')
      .then((d) => {
        setStatus(`後端連線正常 · 目前醫師數 ${d.doctors?.length ?? 0}`)
        setStatusOk(true)
      })
      .catch((e) => {
        setStatus(`無法連線到後端：${e.message}`)
        setStatusOk(false)
      })
  }, [])

  return (
    <>
      <h1 className="page-title">儀表板</h1>
      <p className="page-sub">Phase 0 骨架（Vite + React + Recharts）</p>

      <div
        className="card"
        style={{
          borderColor:
            statusOk === true ? 'var(--ok)' : statusOk === false ? 'var(--err)' : undefined,
        }}
      >
        {status}
      </div>

      <div className="placeholder">各 Phase 功能模組將逐步加入此處</div>
    </>
  )
}
