import { getEnv } from '@/lib/env'

export class ApiError extends Error {
  constructor(status, message) {
    super(message)
    this.status = status
    this.name = 'ApiError'
  }
}

function baseURL() {
  return getEnv('NEXT_PUBLIC_API_URL') || 'http://localhost:8000'
}

async function _fetch(path, options = {}) {
  const res = await fetch(`${baseURL()}${path}`, {
    credentials: 'include',
    headers: { 'Content-Type': 'application/json', ...options.headers },
    ...options,
  })
  if (res.status === 204) return null
  if (!res.ok) {
    const body = await res.json().catch(() => ({ detail: res.statusText }))
    throw new ApiError(res.status, body.detail ?? res.statusText)
  }
  return res.json()
}

// 동시 401 발생 시 refresh 요청을 하나로 collapse
let _refreshPromise = null

async function request(path, options = {}) {
  try {
    return await _fetch(path, options)
  } catch (err) {
    const skip = err.status !== 401 || path === '/auth/refresh' || path === '/auth/login'
    if (skip) throw err

    if (!_refreshPromise) {
      _refreshPromise = _fetch('/auth/refresh', { method: 'POST' }).finally(() => {
        _refreshPromise = null
      })
    }
    try {
      await _refreshPromise
      return await _fetch(path, options)
    } catch {
      if (typeof window !== 'undefined') window.location.href = '/login'
      throw err
    }
  }
}

export const api = {
  auth: {
    login: (email, password) =>
      request('/auth/login', { method: 'POST', body: JSON.stringify({ email, password }) }),
    logout: () => request('/auth/logout', { method: 'POST' }),
    me: () => request('/auth/me'),
  },
}
