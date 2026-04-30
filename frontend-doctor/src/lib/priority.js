// 警示嚴重度 → UI 燈號 / 排序權重
// 後端 alerts.severity: low | medium | high | critical
// UI 燈號（對應 styles/index.css badge）：ok | warn | err | crit

export const SEVERITY_RANK = {
  critical: 4,
  high: 3,
  medium: 2,
  low: 1,
}

export const SEVERITY_TO_BADGE = {
  critical: 'crit',
  high: 'err',
  medium: 'warn',
  low: 'warn',
}

export const SEVERITY_LABEL = {
  critical: '需立即關注',
  high: '需立即關注',
  medium: '需要關注',
  low: '留意',
}

export const ALERT_TYPE_LABEL = {
  er_visit: '急診訪視',
  missed_medication: '漏藥',
  self_discontinued: '自行停藥',
  infection: '感染徵象',
  low_mood: '情緒低落',
  psych_crisis: '心理危機',
  other: '其他',
}

export function worstAlert(alerts) {
  if (!alerts || alerts.length === 0) return null
  return alerts.reduce((best, a) => {
    const r = SEVERITY_RANK[a.severity] ?? 0
    const br = best ? (SEVERITY_RANK[best.severity] ?? 0) : -1
    return r > br ? a : best
  }, null)
}

export function patientPriority(activeAlerts) {
  const worst = worstAlert(activeAlerts)
  if (!worst) {
    return { badge: 'ok', label: '狀況穩定', rank: 0, alert: null }
  }
  return {
    badge: SEVERITY_TO_BADGE[worst.severity] ?? 'warn',
    label: SEVERITY_LABEL[worst.severity] ?? '需要關注',
    rank: SEVERITY_RANK[worst.severity] ?? 0,
    alert: worst,
  }
}
