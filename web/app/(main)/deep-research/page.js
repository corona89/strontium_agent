'use client'

import { useState, useEffect, useCallback, useRef } from 'react'
import { Trash2 } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Group as PanelGroup, Panel, Separator as PanelSeparator } from 'react-resizable-panels'
import { api, ApiError } from '@/lib/api'
import MarkdownRenderer from '@/components/deep-research/MarkdownRenderer'
import useAuthStore from '@/store/auth'

const STATUS_LABEL = {
  draft: '대기',
  awaiting_approval: '승인 대기',
  approved: '승인됨',
  rejected: '거절됨',
  running: '실행 중',
  completed: '완료',
}

export default function DeepResearchPage() {
  const user = useAuthStore((s) => s.user)
  const permissions = user?.permissions || {}
  const canCreate = permissions.deep_research?.create

  const [models, setModels] = useState({ providers: [] })
  const [sessions, setSessions] = useState([])
  const [current, setCurrent] = useState(null)
  const [input, setInput] = useState('')
  const [msg, setMsg] = useState('')
  const [running, setRunning] = useState(false)
  const [liveLog, setLiveLog] = useState([])
  const [newSession, setNewSession] = useState(null)
  const [planDraft, setPlanDraft] = useState(null)
  const [loading, setLoading] = useState(true)
  const scrollRef = useRef(null)
  const abortRef = useRef(null)

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const [m, s] = await Promise.all([
        api.deepResearch.listModels(),
        api.deepResearch.listSessions(),
      ])
      setModels(m)
      setSessions(s)
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

  useEffect(() => {
    if (current?.status === 'awaiting_approval' && current.plan) {
      // eslint-disable-next-line react-hooks/set-state-in-effect
      setPlanDraft(current.plan.map((p) => ({ ...p })))
    } else {
      setPlanDraft(null)
    }
  }, [current?.id, current?.status, current?.plan])

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight
    }
  }, [current?.messages, liveLog])

  useEffect(() => {
    return () => {
      if (abortRef.current) abortRef.current.abort()
    }
  }, [])

  function closeStream() {
    if (abortRef.current) {
      abortRef.current.abort()
      abortRef.current = null
    }
  }

  async function openStream(sessionId) {
    closeStream()
    const ctrl = new AbortController()
    abortRef.current = ctrl
    let stepBuf = ''
    let finished = false
    try {
      await api.deepResearch.streamSession(
        sessionId,
        ({ event, data }) => {
          if (event === 'step_start') {
            stepBuf = ''
            setLiveLog((prev) => [
              ...prev,
              { id: `step-${data.index}`, kind: 'step', title: data.title, text: '' },
            ])
          } else if (event === 'step_delta') {
            stepBuf += data.delta
            setLiveLog((prev) =>
              prev.map((l) => (l.id === `step-${data.index}` ? { ...l, text: stepBuf } : l))
            )
          } else if (event === 'search') {
            setLiveLog((prev) => [
              ...prev,
              { id: `search-${data.index}-${Date.now()}`, kind: 'search', query: data.query },
            ])
          } else if (event === 'final_start') {
            stepBuf = ''
            setLiveLog((prev) => [...prev, { id: 'final', kind: 'final', text: '' }])
          } else if (event === 'final_delta') {
            stepBuf += data.delta
            setLiveLog((prev) => prev.map((l) => (l.id === 'final' ? { ...l, text: stepBuf } : l)))
          } else if (event === 'completed' || event === 'cancelled') {
            finished = true
          } else if (event === 'error') {
            setMsg(data.message)
          }
        },
        ctrl.signal
      )
    } catch (err) {
      if (err?.name !== 'AbortError') {
        setMsg(err instanceof ApiError ? err.message : '스트림 조회에 실패했습니다')
      }
    }
    if (abortRef.current === ctrl) {
      abortRef.current = null
    }
    if (finished) {
      setRunning(false)
      setLiveLog([])
      await selectSession(sessionId)
    }
  }

  async function selectSession(id) {
    closeStream()
    try {
      const detail = await api.deepResearch.getSession(id)
      setCurrent(detail)
      setLiveLog([])
      setMsg('')
      if (detail.status === 'running') {
        setRunning(true)
        openStream(id)
      } else {
        setRunning(false)
      }
    } catch (err) {
      setMsg(err instanceof ApiError ? err.message : '세션 로드에 실패했습니다')
    }
  }

  async function handleCreateSession() {
    if (!newSession?.provider_id || !newSession?.model) {
      setMsg('제공자와 모델을 선택하세요')
      return
    }
    try {
      const s = await api.deepResearch.createSession({
        provider_id: newSession.provider_id,
        model: newSession.model,
      })
      await selectSession(s.id)
      setInput('')
      load()
    } catch (err) {
      setMsg(err instanceof ApiError ? err.message : '세션 생성에 실패했습니다')
    }
  }

  async function handleSend(e) {
    e.preventDefault()
    if (!input.trim() || !current || running) return
    const content = input.trim()
    setInput('')
    try {
      const detail = await api.deepResearch.sendMessage(current.id, content)
      setCurrent(detail)
      load()
    } catch (err) {
      setMsg(err instanceof ApiError ? err.message : '전송에 실패했습니다')
    }
  }

  async function handleDeleteSession(id, e) {
    e.stopPropagation()
    if (!window.confirm('이 조사 이력을 삭제하시겠습니까?')) return
    if (current?.id === id && running) {
      closeStream()
      setRunning(false)
    }
    try {
      await api.deepResearch.deleteSession(id)
      if (current?.id === id) setCurrent(null)
      load()
    } catch (err) {
      setMsg(err instanceof ApiError ? err.message : '삭제에 실패했습니다')
    }
  }

  function updateStep(i, field, value) {
    setPlanDraft((prev) => prev.map((s, idx) => (idx === i ? { ...s, [field]: value } : s)))
  }
  function addStep() {
    setPlanDraft((prev) => [
      ...prev,
      { id: `new-${Date.now()}`, title: '', query: '', done: false },
    ])
  }
  function removeStep(i) {
    setPlanDraft((prev) => prev.filter((_, idx) => idx !== i))
  }

  async function savePlan() {
    try {
      await api.deepResearch.updatePlan(current.id, planDraft)
      await selectSession(current.id)
      setMsg('플랜을 저장했습니다')
    } catch (err) {
      setMsg(err instanceof ApiError ? err.message : '플랜 저장에 실패했습니다')
    }
  }
  async function approve() {
    try {
      await api.deepResearch.approvePlan(current.id)
      await selectSession(current.id)
    } catch (err) {
      setMsg(err instanceof ApiError ? err.message : '승인에 실패했습니다')
    }
  }
  async function reject() {
    try {
      await api.deepResearch.rejectPlan(current.id)
      await selectSession(current.id)
    } catch (err) {
      setMsg(err instanceof ApiError ? err.message : '거절에 실패했습니다')
    }
  }

  async function handleRun() {
    setRunning(true)
    setLiveLog([])
    setMsg('')
    try {
      await api.deepResearch.runSession(current.id)
    } catch (err) {
      setRunning(false)
      setMsg(err instanceof ApiError ? err.message : '실행에 실패했습니다')
      return
    }
    await openStream(current.id)
  }

  const selectedProvider = models.providers.find(
    (p) => p.id === newSession?.provider_id
  )

  function renderMessage(m) {
    if (m.role === 'user' && m.kind === 'text') {
      return (
        <div key={m.id} className="flex justify-end">
          <div className="max-w-[80%] rounded-lg bg-primary px-3 py-2 text-sm text-primary-foreground whitespace-pre-wrap">
            {m.content}
          </div>
        </div>
      )
    }
    if (m.role === 'user' && m.kind === 'plan') {
      return (
        <div key={m.id} className="flex justify-end">
          <div className="max-w-[80%] rounded-lg bg-muted px-3 py-2 text-xs text-muted-foreground">
            플랜 편집됨
          </div>
        </div>
      )
    }
    if (m.role === 'assistant' && m.kind === 'plan') {
      let steps = []
      try {
        steps = JSON.parse(m.content)
      } catch {
        steps = []
      }
      return (
        <div key={m.id} className="rounded-lg border bg-card p-3 text-sm">
          <p className="mb-2 font-medium">조사 플랜 제안</p>
          <ol className="list-decimal space-y-1 pl-5 text-xs">
            {steps.map((s, i) => (
              <li key={i}>
                <span className="font-medium">{s.title}</span>
                {s.query && <span className="text-muted-foreground"> — {s.query}</span>}
              </li>
            ))}
          </ol>
        </div>
      )
    }
    if (m.role === 'assistant' && m.kind === 'final') {
      return (
        <div key={m.id} className="rounded-lg border bg-card p-3 text-sm">
          <p className="mb-2 font-medium">최종 보고서</p>
          <MarkdownRenderer>{m.content}</MarkdownRenderer>
        </div>
      )
    }
    if (m.role === 'assistant' && m.kind === 'step_progress') {
      return (
        <div key={m.id} className="rounded-lg border bg-card p-3 text-sm">
          <MarkdownRenderer>{m.content}</MarkdownRenderer>
        </div>
      )
    }
    return (
      <div key={m.id} className="rounded-lg border bg-card p-3 text-sm">
        <MarkdownRenderer>{m.content}</MarkdownRenderer>
      </div>
    )
  }

  function renderLive(l) {
    if (l.kind === 'search') {
      return (
        <div key={l.id} className="rounded bg-muted px-3 py-1.5 text-xs text-muted-foreground">
          웹 검색 중: {l.query}
        </div>
      )
    }
    return (
      <div key={l.id} className="rounded-lg border bg-card p-3 text-sm whitespace-pre-wrap">
        {l.title && <p className="mb-1 text-xs font-medium text-muted-foreground">{l.title}</p>}
        {l.text}
        {running && <span className="ml-1 animate-pulse">▌</span>}
      </div>
    )
  }

  return (
    <div className="flex h-full flex-col">
      <h1 className="text-2xl font-semibold">딥 리서치 에이전트</h1>

      {msg && <p className="mt-2 text-xs text-destructive">{msg}</p>}

      <PanelGroup orientation="horizontal" className="mt-4 flex-1 overflow-hidden">
        <Panel id="session-list" defaultSize={280} minSize={200} maxSize={480} className="overflow-auto pr-2">
          <Button
            size="sm"
            className="w-full"
            onClick={() => {
              setCurrent(null)
              setNewSession({ provider_id: '', model: '' })
            }}
            disabled={!canCreate}
          >
            새 조사
          </Button>
          <div className="mt-3 space-y-1">
            {sessions.map((s) => (
              <div
                key={s.id}
                className={`group flex items-center rounded transition-colors ${
                  current?.id === s.id
                    ? 'bg-accent text-accent-foreground'
                    : 'hover:bg-accent/50'
                }`}
              >
                <button
                  onClick={() => selectSession(s.id)}
                  className="flex-1 truncate px-2 py-1.5 text-left text-xs"
                >
                  {s.title || s.model}
                  <span className="ml-1 text-[10px] text-muted-foreground">
                    {STATUS_LABEL[s.status]}
                  </span>
                </button>
                {canCreate && (
                  <button
                    onClick={(e) => handleDeleteSession(s.id, e)}
                    className="mr-1 shrink-0 rounded p-1 text-muted-foreground opacity-0 transition-opacity hover:text-destructive group-hover:opacity-100"
                    title="삭제"
                  >
                    <Trash2 size={12} />
                  </button>
                )}
              </div>
            ))}
          </div>
        </Panel>
        <PanelSeparator className="w-1.5 shrink-0 bg-border transition-colors hover:bg-primary/50 data-[separator=active]:bg-primary" />
        <Panel id="chat" className="flex flex-col overflow-hidden">
          {!current ? (
            <div className="flex flex-1 items-center justify-center">
              {newSession ? (
                <div className="w-full max-w-md space-y-3 rounded-lg border bg-card p-4">
                  <h2 className="text-sm font-medium">새 조사 세션</h2>
                  {models.providers.length === 0 ? (
                    <p className="text-xs text-muted-foreground">
                      활성화된 모델이 없습니다. 운영자에게 모델 관리 메뉴에서 제공자와 모델을
                      등록하고 API 키를 설정해달라고 요청하세요.
                    </p>
                  ) : (
                    <>
                      <label className="block text-xs">
                        <span className="mb-1 block text-muted-foreground">제공자</span>
                        <select
                          value={newSession.provider_id}
                          onChange={(e) =>
                            setNewSession({ provider_id: e.target.value, model: '' })
                          }
                          className="w-full rounded-md border bg-background px-3 py-2 text-sm"
                        >
                          <option value="">선택하세요</option>
                          {models.providers.map((p) => (
                            <option key={p.id} value={p.id}>
                              {p.display_name}
                            </option>
                          ))}
                        </select>
                      </label>
                      <label className="block text-xs">
                        <span className="mb-1 block text-muted-foreground">모델</span>
                        <select
                          value={newSession.model}
                          onChange={(e) =>
                            setNewSession({ ...newSession, model: e.target.value })
                          }
                          disabled={!selectedProvider || (selectedProvider?.models || []).length === 0}
                          className="w-full rounded-md border bg-background px-3 py-2 text-sm disabled:opacity-60"
                        >
                          <option value="">선택하세요</option>
                          {(selectedProvider?.models || []).map((m) => (
                            <option key={m} value={m}>
                              {m}
                            </option>
                          ))}
                        </select>
                        {selectedProvider && (selectedProvider.models || []).length === 0 && (
                          <span className="mt-1 block text-[11px] text-destructive">
                            이 제공자에 현재 사용 가능한 모델이 없습니다. API 키를 확인하거나
                            모델 관리에서 사용 가능한 모델 식별자를 등록하세요.
                          </span>
                        )}
                      </label>
                      <Button
                        size="sm"
                        className="w-full"
                        onClick={handleCreateSession}
                        disabled={!newSession.provider_id || !newSession.model}
                      >
                        세션 시작
                      </Button>
                    </>
                  )}
                </div>
              ) : loading ? (
                <p className="text-sm text-muted-foreground">로딩 중...</p>
              ) : (
                <p className="text-sm text-muted-foreground">
                  새 조사를 시작하거나 좌측에서 세션을 선택하세요.
                </p>
              )}
            </div>
          ) : (
            <>
              <div className="mb-2 flex items-center gap-2 text-xs text-muted-foreground">
                <span className="font-medium text-foreground">{current.model}</span>
                <span className="rounded bg-muted px-1.5 py-0.5">
                  {STATUS_LABEL[current.status]}
                </span>
              </div>

              <div ref={scrollRef} className="flex-1 space-y-3 overflow-auto pb-4">
                {current.messages.map(renderMessage)}

                {current.status === 'awaiting_approval' && planDraft && (
                  <div className="rounded-lg border bg-card p-3">
                    <p className="mb-2 text-sm font-medium">플랜 편집 · 승인</p>
                    <div className="space-y-2">
                      {planDraft.map((s, i) => (
                        <div key={s.id} className="flex gap-2">
                          <Input
                            value={s.title}
                            onChange={(e) => updateStep(i, 'title', e.target.value)}
                            placeholder="조사 항목"
                            className="text-xs"
                          />
                          <Input
                            value={s.query || ''}
                            onChange={(e) => updateStep(i, 'query', e.target.value)}
                            placeholder="검색 쿼리 (선택)"
                            className="text-xs"
                          />
                          <Button
                            size="xs"
                            variant="outline"
                            onClick={() => removeStep(i)}
                          >
                            삭제
                          </Button>
                        </div>
                      ))}
                    </div>
                    <div className="mt-3 flex gap-2">
                      <Button size="xs" variant="outline" onClick={addStep}>
                        스텝 추가
                      </Button>
                      <Button size="xs" variant="outline" onClick={savePlan}>
                        저장
                      </Button>
                      <Button size="xs" onClick={approve}>
                        승인
                      </Button>
                      <Button size="xs" variant="destructive" onClick={reject}>
                        거절
                      </Button>
                    </div>
                  </div>
                )}

                {current.status === 'approved' && canCreate && (
                  <div className="flex justify-center">
                    <Button onClick={handleRun} disabled={running}>
                      {running ? '실행 중...' : '조사 실행'}
                    </Button>
                  </div>
                )}

                {liveLog.map(renderLive)}
              </div>

              {current.status === 'draft' && canCreate && (
                <form onSubmit={handleSend} className="flex gap-2 border-t pt-3">
                  <Input
                    value={input}
                    onChange={(e) => setInput(e.target.value)}
                    placeholder="조사할 주제나 질문을 입력하세요"
                    disabled={running}
                  />
                  <Button type="submit" size="sm" disabled={!input.trim() || running}>
                    전송
                  </Button>
                </form>
              )}
            </>
          )}
        </Panel>
      </PanelGroup>
    </div>
  )
}
