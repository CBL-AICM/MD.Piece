import { useMemo } from 'react'

// 把症狀關鍵字對到身體區域 — 越多次紀錄該區越紅
const KEYWORD_MAP = [
  ['head',     ['頭', 'head', '頭痛', '偏頭痛', '頭暈', '眩暈', 'dizz', 'headache']],
  ['eye',      ['眼', 'eye', '視力', '視', 'blur']],
  ['ear',      ['耳', 'ear', '聽力', 'tinnit']],
  ['nose',     ['鼻', '鼻塞', '流鼻', 'nose', 'sneez']],
  ['mouth',    ['口', '嘴', '喉', 'sore throat', '吞嚥', '舌', '唇']],
  ['neck',     ['頸', '脖', 'neck']],
  ['chest',    ['胸', '心', 'chest', 'heart', '心悸', '心律', '心跳']],
  ['lung',     ['肺', '咳', 'cough', '痰', '呼吸', 'breath', '氣促', '喘']],
  ['abdomen',  ['腹', '胃', '肚', '腸', 'nausea', '噁心', '嘔', '腹瀉', '便秘', 'stomach']],
  ['back',     ['背', '腰', 'back', 'lumbar']],
  ['arm-l',    ['左手', '左臂', '左肩']],
  ['arm-r',    ['右手', '右臂', '右肩', '手', '肩', 'arm', 'shoulder']],
  ['leg-l',    ['左腳', '左腿', '左膝']],
  ['leg-r',    ['右腳', '右腿', '右膝', '腳', '腿', '膝', 'leg', 'knee', 'ankle']],
  ['skin',     ['皮膚', '疹', '癢', 'rash', 'itch', 'skin']],
  ['general',  ['疲勞', '倦', 'fatigue', '發燒', 'fever', '畏寒', '冷顫']],
]

function classifySymptom(s) {
  const lower = (s || '').toLowerCase()
  for (const [region, keys] of KEYWORD_MAP) {
    for (const k of keys) {
      if (lower.includes(k.toLowerCase())) return region
    }
  }
  return 'general'
}

export default function BodyHeatmap({ symptoms }) {
  const counts = useMemo(() => {
    const c = {}
    for (const s of symptoms ?? []) {
      const arr = Array.isArray(s.symptoms) ? s.symptoms : []
      for (const sym of arr) {
        const r = classifySymptom(sym)
        c[r] = (c[r] || 0) + 1
      }
    }
    return c
  }, [symptoms])

  const max = Math.max(1, ...Object.values(counts))
  const fill = (region) => {
    const v = counts[region] || 0
    if (v === 0) return 'rgba(110,168,255,0.08)'
    const t = v / max
    // 從藍 (#6ea8ff) 漸到紅 (#ff3d6a)
    const r = Math.round(110 + (255 - 110) * t)
    const g = Math.round(168 + (61 - 168) * t)
    const b = Math.round(255 + (106 - 255) * t)
    return `rgba(${r},${g},${b},${0.45 + 0.5 * t})`
  }
  const stroke = 'rgba(255,255,255,0.18)'

  const Region = ({ id, label, ...props }) => {
    const v = counts[id] || 0
    return (
      <g>
        <path {...props} fill={fill(id)} stroke={stroke} strokeWidth={1}>
          <title>{label} · {v} 次</title>
        </path>
      </g>
    )
  }

  const total = Object.values(counts).reduce((a, b) => a + b, 0)

  return (
    <div className="body-heatmap">
      <div className="body-svg-wrap">
        <svg viewBox="0 0 200 460" className="body-svg" xmlns="http://www.w3.org/2000/svg">
          {/* 頭 */}
          <Region id="head" label="頭部"
            d="M 100 10 C 75 10 65 35 65 55 C 65 80 80 95 100 95 C 120 95 135 80 135 55 C 135 35 125 10 100 10 Z" />
          {/* 眼睛 / 耳朵 / 鼻子 / 嘴 — 小圓 */}
          <Region id="eye" label="眼" d="M 80 45 a 4 4 0 1 0 8 0 a 4 4 0 1 0 -8 0 Z M 112 45 a 4 4 0 1 0 8 0 a 4 4 0 1 0 -8 0 Z" />
          <Region id="nose" label="鼻" d="M 96 60 L 100 72 L 104 60 Z" />
          <Region id="ear" label="耳" d="M 60 50 q -8 5 -2 18 q 4 0 6 -2 Z M 140 50 q 8 5 2 18 q -4 0 -6 -2 Z" />
          <Region id="mouth" label="口/喉" d="M 86 80 q 14 7 28 0 q -2 6 -14 6 q -12 0 -14 -6 Z" />
          {/* 頸 */}
          <Region id="neck" label="頸部"
            d="M 86 95 L 86 110 L 114 110 L 114 95 Z" />
          {/* 胸 */}
          <Region id="chest" label="胸（心臟附近）"
            d="M 60 110 L 140 110 L 142 165 L 58 165 Z" />
          {/* 肺 — 重疊在胸的兩側半透明 */}
          <Region id="lung" label="肺/呼吸"
            d="M 64 115 L 96 115 L 96 158 L 60 158 Z M 104 115 L 136 115 L 140 158 L 104 158 Z" />
          {/* 腹 */}
          <Region id="abdomen" label="腹/胃腸"
            d="M 60 165 L 140 165 L 138 230 L 62 230 Z" />
          {/* 左右手臂 */}
          <Region id="arm-r" label="右上肢"
            d="M 140 110 L 165 115 L 175 200 L 168 250 L 158 250 L 152 200 L 140 165 Z" />
          <Region id="arm-l" label="左上肢"
            d="M 60 110 L 35 115 L 25 200 L 32 250 L 42 250 L 48 200 L 60 165 Z" />
          {/* 左右腿 */}
          <Region id="leg-r" label="右下肢"
            d="M 102 230 L 138 230 L 140 350 L 130 440 L 108 440 L 102 350 Z" />
          <Region id="leg-l" label="左下肢"
            d="M 62 230 L 98 230 L 98 350 L 92 440 L 70 440 L 60 350 Z" />
          {/* 背（顯示為環狀外框 — 概念性 fallback） */}
          <Region id="back" label="背/腰"
            d="M 62 175 L 138 175 L 138 215 L 62 215 Z" style={{ display: 'none' }} />
          {/* 皮膚 — 用全身淡色覆蓋 */}
          <Region id="skin" label="皮膚（疹/癢）"
            d="M 50 100 L 150 100 L 150 440 L 50 440 Z" style={{ display: 'none' }} />
        </svg>
      </div>

      <div className="body-legend">
        <h4>區域熱點</h4>
        <p className="cell-dim" style={{ marginTop: 0 }}>
          越痛越紅 — 滑鼠移到部位顯示次數。共統計到 <strong>{total}</strong> 筆症狀。
        </p>
        <ul className="body-region-list">
          {[...KEYWORD_MAP.map((m) => m[0])].map((id) => {
            const v = counts[id] || 0
            if (v === 0) return null
            return (
              <li key={id}>
                <span className="body-region-dot" style={{ background: fill(id) }} />
                <span className="body-region-name">{regionName(id)}</span>
                <span className="body-region-count">{v} 次</span>
              </li>
            )
          })}
          {total === 0 && <li className="cell-dim">尚無症狀紀錄</li>}
        </ul>
        <p className="body-disclaimer">
          區域對應為關鍵字啟發式分類，僅供視覺化參考。
        </p>
      </div>
    </div>
  )
}

function regionName(id) {
  return ({
    head: '頭部', eye: '眼睛', ear: '耳朵', nose: '鼻', mouth: '口/喉',
    neck: '頸部', chest: '胸/心', lung: '肺/呼吸', abdomen: '腹/胃腸',
    back: '背/腰', 'arm-l': '左上肢', 'arm-r': '右上肢',
    'leg-l': '左下肢', 'leg-r': '右下肢', skin: '皮膚', general: '全身性',
  })[id] || id
}
