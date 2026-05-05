// 醫師端 auth — 走患者端共用的 /auth/login + /auth/register
// role 強制為 'doctor'，需要通行碼 310530
import { apiPost, setActiveDoctorId } from './api.js'

const USER_KEY = 'mdp.doctorUser'
const PROFILE_KEY = 'mdp.doctorProfile' // gender / birthday — 後端 users 表沒這兩欄，存本機

export function getCurrentUser() {
  if (typeof window === 'undefined') return null
  try {
    const raw = window.localStorage.getItem(USER_KEY)
    return raw ? JSON.parse(raw) : null
  } catch {
    return null
  }
}

function setCurrentUser(user) {
  if (typeof window === 'undefined') return
  if (user) window.localStorage.setItem(USER_KEY, JSON.stringify(user))
  else window.localStorage.removeItem(USER_KEY)
}

export function getDoctorProfile() {
  if (typeof window === 'undefined') return {}
  try {
    const raw = window.localStorage.getItem(PROFILE_KEY)
    return raw ? JSON.parse(raw) : {}
  } catch {
    return {}
  }
}

function setDoctorProfile(profile) {
  if (typeof window === 'undefined') return
  if (profile) window.localStorage.setItem(PROFILE_KEY, JSON.stringify(profile))
  else window.localStorage.removeItem(PROFILE_KEY)
}

export function isAuthed() {
  const u = getCurrentUser()
  return !!u && u.role === 'doctor'
}

export function logout() {
  setCurrentUser(null)
  setDoctorProfile(null)
  setActiveDoctorId(null)
}

export async function loginDoctor({ username, password, doctor_key }) {
  const user = await apiPost('/auth/login', {
    username, password, doctor_key,
  })
  if (user.role !== 'doctor') {
    throw new Error('此帳號不是醫師身份')
  }
  setCurrentUser(user)
  return user
}

export async function registerDoctor({
  username, password, nickname, doctor_key,
  specialty, gender, birthday, phone,
}) {
  const user = await apiPost('/auth/register', {
    username, password, nickname,
    role: 'doctor',
    doctor_key,
  })
  setCurrentUser(user)
  setDoctorProfile({ gender, birthday, specialty, phone })
  // 同步建立 /doctors/ 的臨床醫師檔，讓 Settings.jsx 的醫師列表能掛上身份
  try {
    const created = await apiPost('/doctors/', {
      name: nickname,
      specialty: specialty || '未填',
      phone: phone || null,
    })
    if (created?.id) setActiveDoctorId(created.id)
  } catch {
    // 後端若沒接 doctors 表也不阻斷註冊
  }
  return user
}
