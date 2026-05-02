import { clearSession, getToken } from './auth.js'

// 用 ?? 而不是 ||：production build 同源呼叫時 VITE_API_URL 是空字串，
// 我們希望保留空字串而不要 fallback 到 '/api'（dev 才需要 '/api' 走 Vite proxy）
const DEFAULT_API = import.meta.env.VITE_API_URL ?? '/api'

export function getApiBase() {
  if (typeof window !== 'undefined') {
    const override = window.localStorage.getItem('mdp.apiBase')
    if (override) return override
  }
  return DEFAULT_API
}

export function setApiBase(url) {
  if (typeof window === 'undefined') return
  if (url) window.localStorage.setItem('mdp.apiBase', url)
  else window.localStorage.removeItem('mdp.apiBase')
}

export function getActiveDoctorId() {
  if (typeof window === 'undefined') return null
  return window.localStorage.getItem('mdp.doctorId')
}

export function setActiveDoctorId(id) {
  if (typeof window === 'undefined') return
  if (id) window.localStorage.setItem('mdp.doctorId', id)
  else window.localStorage.removeItem('mdp.doctorId')
}

function buildUrl(path, params) {
  const base = getApiBase()
  if (!params) return `${base}${path}`
  const qs = new URLSearchParams()
  for (const [k, v] of Object.entries(params)) {
    if (v === undefined || v === null || v === '') continue
    qs.set(k, String(v))
  }
  const tail = qs.toString()
  return tail ? `${base}${path}?${tail}` : `${base}${path}`
}

function authHeaders(extra = {}) {
  const token = getToken()
  return token ? { ...extra, Authorization: `Bearer ${token}` } : extra
}

async function handle(res, method, path) {
  if (res.status === 401) {
    clearSession()
    if (typeof window !== 'undefined' && !window.location.pathname.endsWith('/login')) {
      const base = import.meta.env.BASE_URL.replace(/\/$/, '') || ''
      window.location.replace(`${base}/login`)
    }
    throw new Error(`${method} ${path} → 401 未登入`)
  }
  if (!res.ok) {
    let detail = ''
    try {
      const body = await res.json()
      detail = body?.detail ? ` — ${body.detail}` : ''
    } catch {
      // ignore
    }
    throw new Error(`${method} ${path} → ${res.status}${detail}`)
  }
  if (res.status === 204) return null
  return res.json()
}

export async function apiGet(path, params) {
  const url = buildUrl(path, params)
  const res = await fetch(url, { headers: authHeaders() })
  return handle(res, 'GET', path)
}

export async function apiPost(path, body) {
  const res = await fetch(buildUrl(path), {
    method: 'POST',
    headers: authHeaders({ 'Content-Type': 'application/json' }),
    body: JSON.stringify(body ?? {}),
  })
  return handle(res, 'POST', path)
}

export async function apiPut(path, body) {
  const res = await fetch(buildUrl(path), {
    method: 'PUT',
    headers: authHeaders({ 'Content-Type': 'application/json' }),
    body: JSON.stringify(body ?? {}),
  })
  return handle(res, 'PUT', path)
}

export async function apiDelete(path) {
  const res = await fetch(buildUrl(path), {
    method: 'DELETE',
    headers: authHeaders(),
  })
  return handle(res, 'DELETE', path)
}
