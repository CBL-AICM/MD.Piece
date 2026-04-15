// Mock 資料 — Phase 4 會替換為真正 API
// 產生近 N 天的情緒、症狀、順從率趨勢（0-100）

function rand(seed) {
  const x = Math.sin(seed) * 10000
  return x - Math.floor(x)
}

export function generateTrendData(days = 30) {
  const today = new Date()
  return Array.from({ length: days }, (_, i) => {
    const d = new Date(today)
    d.setDate(today.getDate() - (days - 1 - i))
    const emotion = Math.round(50 + 25 * Math.sin(i / 4) + (rand(i) - 0.5) * 15)
    const symptom = Math.round(60 - 20 * Math.sin(i / 5) + (rand(i + 10) - 0.5) * 18)
    const adherence = Math.round(88 + 8 * Math.sin(i / 6) + (rand(i + 20) - 0.5) * 10)
    return {
      date: `${d.getMonth() + 1}/${d.getDate()}`,
      emotion: Math.max(0, Math.min(100, emotion)),
      symptom: Math.max(0, Math.min(100, symptom)),
      adherence: Math.max(0, Math.min(100, adherence)),
    }
  })
}

export const mockSummary = {
  activePatients: 24,
  alertsToday: 3,
  pendingNotes: 5,
  avgAdherence: 87,
}
