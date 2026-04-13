import { useParams } from 'react-router-dom'

export default function PatientDetail() {
  const { id } = useParams()
  return (
    <>
      <h1 className="page-title">患者詳情</h1>
      <p className="page-sub">ID: {id}</p>
      <div className="placeholder">
        Phase 3：快速預覽 · 時間軸 · 備註<br />
        Phase 4：30 天整合報告 · 調藥追蹤 · 跨回診比較
      </div>
    </>
  )
}
