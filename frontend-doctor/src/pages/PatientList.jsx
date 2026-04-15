const MOCK = [
  { id: 'p1', name: '王小明', age: 62, priority: 'crit', lastVisit: '3/28', note: 'ER 訪視 · 連續 2 日漏藥' },
  { id: 'p2', name: '林美華', age: 54, priority: 'err', lastVisit: '4/02', note: '情緒分數低於基線' },
  { id: 'p3', name: '陳志強', age: 47, priority: 'warn', lastVisit: '4/08', note: '劑量調整後待追蹤' },
  { id: 'p4', name: '張淑芬', age: 71, priority: 'warn', lastVisit: '3/30', note: '疼痛評分上升' },
  { id: 'p5', name: '李家興', age: 38, priority: 'ok', lastVisit: '4/10', note: '穩定' },
  { id: 'p6', name: '黃雅婷', age: 29, priority: 'ok', lastVisit: '4/09', note: '穩定' },
]

const LABEL = {
  crit: '需立即關注',
  err: '需立即關注',
  warn: '需要關注',
  ok: '狀況穩定',
}

export default function PatientList() {
  return (
    <>
      <h1 className="page-title">患者清單</h1>
      <p className="page-sub">依需要關注程度自動排序（示範資料）</p>

      <div className="card" style={{ padding: 0 }}>
        <table style={{ width: '100%', borderCollapse: 'collapse' }}>
          <thead>
            <tr style={{ color: 'var(--text-dim)', fontSize: 12, textTransform: 'uppercase', letterSpacing: 1 }}>
              <th style={th}>狀態</th>
              <th style={th}>姓名</th>
              <th style={th}>年齡</th>
              <th style={th}>上次回診</th>
              <th style={th}>重點</th>
            </tr>
          </thead>
          <tbody>
            {MOCK.map((p) => (
              <tr key={p.id} style={{ borderTop: '1px solid var(--border)' }}>
                <td style={td}><span className={`badge ${p.priority}`}>{LABEL[p.priority]}</span></td>
                <td style={{ ...td, fontWeight: 600 }}>{p.name}</td>
                <td style={td}>{p.age}</td>
                <td style={{ ...td, color: 'var(--text-dim)' }}>{p.lastVisit}</td>
                <td style={{ ...td, color: 'var(--text-dim)' }}>{p.note}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <p style={{ marginTop: 12, fontSize: 12, color: 'var(--text-faint)' }}>
        * 示範資料，Phase 2 會接上實際患者與警示系統
      </p>
    </>
  )
}

const th = { textAlign: 'left', padding: '14px 20px', fontWeight: 600 }
const td = { padding: '14px 20px', fontSize: 14 }
