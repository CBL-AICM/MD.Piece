// 把患者列表來源拼起來：clinical 的 /patients/ 表 + auth 的 /auth/users (role=patient)
// 兩邊都可能存在，以 patients 表為主，user-only 的轉成虛擬 patient 紀錄
import { apiGet } from './api.js'

export function userToPatient(u) {
  return {
    id: u.id,
    name: u.nickname || u.username || '未命名',
    age: null,
    gender: null,
    phone: null,
    icd10_codes: [],
    avatar_url: u.avatar_url || null,
    avatar_color: u.avatar_color || null,
    username: u.username,
    created_at: u.created_at,
    _source: 'user',
  }
}

export async function fetchAllPatients() {
  const [pRes, uRes] = await Promise.all([
    apiGet('/patients/').catch(() => ({ patients: [] })),
    apiGet('/auth/users').catch(() => ({ users: [] })),
  ])
  const patients = pRes.patients ?? []
  const users = (uRes.users ?? []).filter((u) => u.role === 'patient')
  const seen = new Set(patients.map((p) => p.id))
  const merged = patients.map((p) => ({ ...p, _source: 'patient' }))
  for (const u of users) {
    if (!seen.has(u.id)) merged.push(userToPatient(u))
  }
  return merged
}

export async function fetchPatientById(id) {
  // 優先試 patients 表；找不到就退回 users 表把 user 變成虛擬 patient
  try {
    const p = await apiGet(`/patients/${id}`)
    return { ...p, _source: 'patient' }
  } catch {
    try {
      const u = await apiGet(`/auth/user/${id}`)
      return userToPatient(u)
    } catch {
      throw new Error(`找不到病患 ${id?.slice(0, 8) ?? ''}`)
    }
  }
}
