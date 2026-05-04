// 醫師端：每位醫師看過哪些 push（doctor_note id）的本地狀態
// 跨裝置同步沒有也沒關係 — 因為是「個人視覺輔助」性質
import { getCurrentUser } from './auth.js'

function key() {
  const u = getCurrentUser()
  return u?.id ? `mdp.readPushes.${u.id}` : null
}

export function getReadSet() {
  const k = key()
  if (!k || typeof window === 'undefined') return new Set()
  try {
    const raw = window.localStorage.getItem(k)
    return new Set(raw ? JSON.parse(raw) : [])
  } catch {
    return new Set()
  }
}

export function markRead(noteIds) {
  const k = key()
  if (!k || typeof window === 'undefined') return
  const set = getReadSet()
  for (const id of noteIds) set.add(id)
  try { window.localStorage.setItem(k, JSON.stringify([...set])) } catch { /* ignore */ }
}

export function unreadCount(notes) {
  const set = getReadSet()
  return (notes || []).filter((n) =>
    Array.isArray(n.tags) && n.tags.includes('patient_push') && !set.has(n.id),
  ).length
}
