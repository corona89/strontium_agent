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

function _parseSSE(raw) {
  let event = 'message'
  let dataStr = ''
  for (const line of raw.split('\n')) {
    if (line.startsWith('event:')) event = line.slice(6).trim()
    else if (line.startsWith('data:')) dataStr += line.slice(5).trim()
  }
  if (!dataStr) return null
  let data
  try {
    data = JSON.parse(dataStr)
  } catch {
    data = dataStr
  }
  return { event, data }
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
  const text = await res.text()
  return text ? JSON.parse(text) : null
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
  models: {
    listProviders: () => request('/models/providers'),
    createProvider: (data) =>
      request('/models/providers', { method: 'POST', body: JSON.stringify(data) }),
    updateProvider: (id, data) =>
      request(`/models/providers/${id}`, { method: 'PATCH', body: JSON.stringify(data) }),
    removeProvider: (id) => request(`/models/providers/${id}`, { method: 'DELETE' }),
  },
  deepResearch: {
    listModels: () => request('/deep-research/models'),
    createSession: (data) =>
      request('/deep-research/sessions', { method: 'POST', body: JSON.stringify(data) }),
    listSessions: () => request('/deep-research/sessions'),
    getSession: (id) => request(`/deep-research/sessions/${id}`),
    deleteSession: (id) => request(`/deep-research/sessions/${id}`, { method: 'DELETE' }),
    sendMessage: (id, content) =>
      request(`/deep-research/sessions/${id}/messages`, {
        method: 'POST',
        body: JSON.stringify({ content }),
      }),
    updatePlan: (id, steps) =>
      request(`/deep-research/sessions/${id}/plan`, {
        method: 'PUT',
        body: JSON.stringify({ steps }),
      }),
    approvePlan: (id) => request(`/deep-research/sessions/${id}/plan/approve`, { method: 'POST' }),
    rejectPlan: (id) => request(`/deep-research/sessions/${id}/plan/reject`, { method: 'POST' }),
    runSession: (id) => request(`/deep-research/sessions/${id}/run`, { method: 'POST' }),
    streamSession: async (id, onEvent, signal) => {
      const res = await fetch(`${baseURL()}/deep-research/sessions/${id}/stream`, {
        method: 'GET',
        credentials: 'include',
        headers: { Accept: 'text/event-stream' },
        signal,
      })
      if (!res.ok) {
        const body = await res.json().catch(() => ({ detail: res.statusText }))
        throw new ApiError(res.status, body.detail ?? res.statusText)
      }
      const reader = res.body.getReader()
      const decoder = new TextDecoder()
      let buffer = ''
      while (true) {
        const { done, value } = await reader.read()
        if (done) break
        buffer += decoder.decode(value, { stream: true })
        let idx
        while ((idx = buffer.indexOf('\n\n')) !== -1) {
          const raw = buffer.slice(0, idx)
          buffer = buffer.slice(idx + 2)
          const evt = _parseSSE(raw)
          if (evt) onEvent(evt)
        }
      }
    },
  },
  llmwiki: {
    listModels: () => request('/llmwiki/models'),
    listWikis: () => request('/llmwiki/wikis'),
    createWiki: (data) =>
      request('/llmwiki/wikis', { method: 'POST', body: JSON.stringify(data) }),
    getWiki: (id) => request(`/llmwiki/wikis/${id}`),
    updateWiki: (id, data) =>
      request(`/llmwiki/wikis/${id}`, { method: 'PATCH', body: JSON.stringify(data) }),
    deleteWiki: (id) => request(`/llmwiki/wikis/${id}`, { method: 'DELETE' }),
    createCategory: (wikiId, name) =>
      request(`/llmwiki/wikis/${wikiId}/categories`, {
        method: 'POST',
        body: JSON.stringify({ name }),
      }),
    updateCategory: (wikiId, catId, name) =>
      request(`/llmwiki/wikis/${wikiId}/categories/${catId}`, {
        method: 'PATCH',
        body: JSON.stringify({ name }),
      }),
    deleteCategory: (wikiId, catId) =>
      request(`/llmwiki/wikis/${wikiId}/categories/${catId}`, { method: 'DELETE' }),
    createPage: (wikiId, data) =>
      request(`/llmwiki/wikis/${wikiId}/pages`, {
        method: 'POST',
        body: JSON.stringify(data),
      }),
    getPage: (wikiId, pageId) => request(`/llmwiki/wikis/${wikiId}/pages/${pageId}`),
    updatePage: (wikiId, pageId, data) =>
      request(`/llmwiki/wikis/${wikiId}/pages/${pageId}`, {
        method: 'PUT',
        body: JSON.stringify(data),
      }),
    deletePage: (wikiId, pageId) =>
      request(`/llmwiki/wikis/${wikiId}/pages/${pageId}`, { method: 'DELETE' }),
    ingest: (wikiId, formData) =>
      request(`/llmwiki/wikis/${wikiId}/ingest`, {
        method: 'POST',
        body: formData,
        headers: {},
      }),
    attachmentUrl: (wikiId, name) =>
      `${baseURL()}/llmwiki/wikis/${wikiId}/attachments/${name}`,
    listMessages: (wikiId) => request(`/llmwiki/wikis/${wikiId}/messages`),
    clearMessages: (wikiId) =>
      request(`/llmwiki/wikis/${wikiId}/messages`, { method: 'DELETE' }),
    chat: async (wikiId, question, onEvent, signal) => {
      const res = await fetch(`${baseURL()}/llmwiki/wikis/${wikiId}/chat`, {
        method: 'POST',
        credentials: 'include',
        headers: { 'Content-Type': 'application/json', Accept: 'text/event-stream' },
        body: JSON.stringify({ question }),
        signal,
      })
      if (!res.ok) {
        const body = await res.json().catch(() => ({ detail: res.statusText }))
        throw new ApiError(res.status, body.detail ?? res.statusText)
      }
      const reader = res.body.getReader()
      const decoder = new TextDecoder()
      let buffer = ''
      while (true) {
        const { done, value } = await reader.read()
        if (done) break
        buffer += decoder.decode(value, { stream: true })
        let idx
        while ((idx = buffer.indexOf('\n\n')) !== -1) {
          const raw = buffer.slice(0, idx)
          buffer = buffer.slice(idx + 2)
          const evt = _parseSSE(raw)
          if (evt) onEvent(evt)
        }
      }
    },
    listDeepResearchSessions: () => request('/deep-research/sessions'),
  },
}
