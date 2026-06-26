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
    googleUrl: () => `${baseURL()}/auth/google`,
  },
  accounts: {
    create: (email, password, nickname) =>
      request('/accounts', {
        method: 'POST',
        body: JSON.stringify({ email, password, nickname }),
      }),
    update: (id, data) =>
      request(`/accounts/${id}`, { method: 'PATCH', body: JSON.stringify(data) }),
    deactivate: (id) => request(`/accounts/${id}`, { method: 'DELETE' }),
  },
  roles: {
    list: () => request('/roles'),
    create: (name, description) =>
      request('/roles', { method: 'POST', body: JSON.stringify({ name, description }) }),
    update: (id, data) =>
      request(`/roles/${id}`, { method: 'PATCH', body: JSON.stringify(data) }),
    remove: (id) => request(`/roles/${id}`, { method: 'DELETE' }),
    setFunctions: (id, entries) =>
      request(`/roles/${id}/functions`, { method: 'PUT', body: JSON.stringify(entries) }),
  },
  functions: {
    list: () => request('/functions'),
    create: (name, description) =>
      request('/functions', { method: 'POST', body: JSON.stringify({ name, description }) }),
    update: (id, data) =>
      request(`/functions/${id}`, { method: 'PATCH', body: JSON.stringify(data) }),
    remove: (id) => request(`/functions/${id}`, { method: 'DELETE' }),
  },
  admin: {
    listUsers: (page = 1, pageSize = 20) =>
      request(`/admin/users?page=${page}&page_size=${pageSize}`),
    updateUserRoles: (userId, roleIds) =>
      request(`/admin/users/${userId}/roles`, {
        method: 'PATCH',
        body: JSON.stringify({ role_ids: roleIds }),
      }),
    resetUserPassword: (userId) =>
      request(`/admin/users/${userId}/reset-password`, { method: 'POST' }),
    deactivateUser: (userId) =>
      request(`/admin/users/${userId}`, { method: 'DELETE' }),
    auditLogs: (page = 1, pageSize = 20) =>
      request(`/admin/audit-logs?page=${page}&page_size=${pageSize}`),
  },
}
