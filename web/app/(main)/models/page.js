'use client'

import { useState, useEffect, useCallback } from 'react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Separator } from '@/components/ui/separator'
import { api, ApiError } from '@/lib/api'
import useAuthStore from '@/store/auth'

const PROVIDER_TYPES = [
  { value: 'ollama_cloud', label: 'Ollama Cloud' },
  { value: 'opencode_zen', label: 'OpenCode Zen' },
]

const emptyForm = {
  provider_type: 'ollama_cloud',
  display_name: '',
  base_url: '',
  modelsText: '',
  is_active: true,
}

export default function ModelsPage() {
  const user = useAuthStore((s) => s.user)
  const permissions = user?.permissions || {}
  const canCreate = permissions.models?.create
  const canUpdate = permissions.models?.update
  const canDelete = permissions.models?.delete

  const [providers, setProviders] = useState([])
  const [loading, setLoading] = useState(true)
  const [msg, setMsg] = useState('')
  const [form, setForm] = useState(emptyForm)
  const [editingId, setEditingId] = useState(null)
  const [showForm, setShowForm] = useState(false)

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const data = await api.models.listProviders()
      setProviders(data)
    } catch (err) {
      setMsg(err instanceof ApiError ? err.message : '로드에 실패했습니다')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    load()
  }, [load])

  function startCreate() {
    setForm(emptyForm)
    setEditingId(null)
    setShowForm(true)
  }

  function startEdit(p) {
    setForm({
      provider_type: p.provider_type,
      display_name: p.display_name,
      base_url: p.base_url || '',
      modelsText: (p.models || []).join('\n'),
      is_active: p.is_active,
    })
    setEditingId(p.id)
    setShowForm(true)
  }

  function closeForm() {
    setShowForm(false)
    setEditingId(null)
    setForm(emptyForm)
  }

  async function handleSubmit(e) {
    e.preventDefault()
    const models = form.modelsText
      .split('\n')
      .map((m) => m.trim())
      .filter(Boolean)
    if (!form.display_name.trim() || models.length === 0) {
      setMsg('표시명과 최소 한 개의 모델이 필요합니다')
      return
    }
    try {
      if (editingId) {
        await api.models.updateProvider(editingId, {
          display_name: form.display_name,
          base_url: form.base_url || null,
          models,
          is_active: form.is_active,
        })
        setMsg('제공자를 수정했습니다')
      } else {
        await api.models.createProvider({
          provider_type: form.provider_type,
          display_name: form.display_name,
          base_url: form.base_url || null,
          models,
          is_active: form.is_active,
        })
        setMsg('제공자를 추가했습니다')
      }
      closeForm()
      load()
    } catch (err) {
      setMsg(err instanceof ApiError ? err.message : '저장에 실패했습니다')
    }
  }

  async function handleDelete(id) {
    if (!window.confirm('이 제공자를 삭제하시겠습니까?')) return
    try {
      await api.models.removeProvider(id)
      setMsg('제공자를 삭제했습니다')
      load()
    } catch (err) {
      setMsg(err instanceof ApiError ? err.message : '삭제에 실패했습니다')
    }
  }

  async function toggleActive(p) {
    try {
      await api.models.updateProvider(p.id, { is_active: !p.is_active })
      load()
    } catch (err) {
      setMsg(err instanceof ApiError ? err.message : '상태 변경에 실패했습니다')
    }
  }

  return (
    <div>
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-semibold">모델 관리</h1>
        {canCreate && !showForm && (
          <Button size="sm" onClick={startCreate}>
            제공자 추가
          </Button>
        )}
      </div>
      <p className="mt-1 text-sm text-muted-foreground">
        LLM 제공자와 모델을 관리합니다. API 키는 환경변수로 관리됩니다.
      </p>

      {msg && <p className="mt-3 text-xs text-muted-foreground">{msg}</p>}

      {showForm && (
        <form onSubmit={handleSubmit} className="mt-6 space-y-3 rounded-lg border bg-card p-4">
          <h2 className="text-sm font-medium">{editingId ? '제공자 수정' : '제공자 추가'}</h2>
          <div className="grid gap-3 sm:grid-cols-2">
            <label className="text-xs">
              <span className="mb-1 block text-muted-foreground">제공자 타입</span>
              <select
                value={form.provider_type}
                onChange={(e) => setForm({ ...form, provider_type: e.target.value })}
                disabled={!!editingId}
                className="w-full rounded-md border bg-background px-3 py-2 text-sm disabled:opacity-60"
              >
                {PROVIDER_TYPES.map((t) => (
                  <option key={t.value} value={t.value}>
                    {t.label}
                  </option>
                ))}
              </select>
            </label>
            <label className="text-xs">
              <span className="mb-1 block text-muted-foreground">표시명</span>
              <Input
                value={form.display_name}
                onChange={(e) => setForm({ ...form, display_name: e.target.value })}
                placeholder="예: Ollama Cloud (운영)"
              />
            </label>
          </div>
          <label className="block text-xs">
            <span className="mb-1 block text-muted-foreground">Base URL (선택)</span>
            <Input
              value={form.base_url}
              onChange={(e) => setForm({ ...form, base_url: e.target.value })}
              placeholder="https://ollama.com"
            />
          </label>
          <label className="block text-xs">
            <span className="mb-1 block text-muted-foreground">
              모델 식별자 (한 줄당 한 개)
            </span>
            <textarea
              value={form.modelsText}
              onChange={(e) => setForm({ ...form, modelsText: e.target.value })}
              placeholder={'gpt-oss:120b\ngpt-oss:20b'}
              rows={4}
              className="w-full rounded-md border bg-background px-3 py-2 text-sm font-mono"
            />
          </label>
          <label className="flex items-center gap-2 text-xs">
            <input
              type="checkbox"
              checked={form.is_active}
              onChange={(e) => setForm({ ...form, is_active: e.target.checked })}
            />
            <span>활성화 (활성화된 제공자의 모델만 딥 리서치에 노출)</span>
          </label>
          <div className="flex justify-end gap-2">
            <Button type="button" size="sm" variant="outline" onClick={closeForm}>
              취소
            </Button>
            <Button type="submit" size="sm">
              {editingId ? '수정' : '추가'}
            </Button>
          </div>
        </form>
      )}

      <Separator className="my-6" />

      {loading ? (
        <p className="text-sm text-muted-foreground">로딩 중...</p>
      ) : providers.length === 0 ? (
        <p className="text-sm text-muted-foreground">등록된 제공자가 없습니다.</p>
      ) : (
        <div className="space-y-3">
          {providers.map((p) => (
            <div key={p.id} className="rounded-lg border bg-card p-4">
              <div className="flex items-start justify-between">
                <div>
                  <div className="flex items-center gap-2">
                    <span className="font-medium">{p.display_name}</span>
                    <span className="rounded bg-muted px-1.5 py-0.5 text-[10px] text-muted-foreground">
                      {p.provider_type}
                    </span>
                    <span
                      className={`rounded px-1.5 py-0.5 text-[10px] ${
                        p.is_active
                          ? 'bg-primary/10 text-primary'
                          : 'bg-muted text-muted-foreground'
                      }`}
                    >
                      {p.is_active ? '활성' : '비활성'}
                    </span>
                    <span
                      className={`rounded px-1.5 py-0.5 text-[10px] ${
                        p.api_key_configured
                          ? 'bg-primary/10 text-primary'
                          : 'bg-destructive/10 text-destructive'
                      }`}
                      title="환경변수 API 키 설정 여부"
                    >
                      {p.api_key_configured ? '키 설정됨' : '키 미설정'}
                    </span>
                  </div>
                  {p.base_url && (
                    <p className="mt-1 text-xs text-muted-foreground">{p.base_url}</p>
                  )}
                  <div className="mt-2 flex flex-wrap gap-1">
                    {(p.models || []).map((m) => (
                      <span
                        key={m}
                        className="rounded bg-muted px-1.5 py-0.5 font-mono text-[10px]"
                      >
                        {m}
                      </span>
                    ))}
                  </div>
                </div>
                <div className="flex gap-1">
                  {canUpdate && (
                    <>
                      <Button size="xs" variant="outline" onClick={() => toggleActive(p)}>
                        {p.is_active ? '비활성화' : '활성화'}
                      </Button>
                      <Button size="xs" variant="outline" onClick={() => startEdit(p)}>
                        수정
                      </Button>
                    </>
                  )}
                  {canDelete && (
                    <Button size="xs" variant="destructive" onClick={() => handleDelete(p.id)}>
                      삭제
                    </Button>
                  )}
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
