'use client'

import { useState, useEffect, useCallback, useRef } from 'react'
import {
  BookOpen,
  ChevronDown,
  ChevronRight,
  FilePlus,
  FolderPlus,
  Pencil,
  Plus,
  Trash2,
  Upload,
  X,
} from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import {
  Group as PanelGroup,
  Panel,
  Separator as PanelSeparator,
} from 'react-resizable-panels'
import { api, ApiError } from '@/lib/api'
import MarkdownRenderer from '@/components/markdown/MarkdownRenderer'
import useAuthStore from '@/store/auth'

const SOURCE_LABEL = {
  md: 'MD',
  deepresearch: '리서치',
  pdf: 'PDF',
  image: '이미지',
  youtube: 'YouTube',
  manual: '문서',
}

export default function LlmWikiPage() {
  const user = useAuthStore((s) => s.user)
  const permissions = user?.permissions || {}
  const canCreate = permissions.llmwiki?.create
  const canUpdate = permissions.llmwiki?.update
  const canDelete = permissions.llmwiki?.delete

  const [models, setModels] = useState({ providers: [] })
  const [wikis, setWikis] = useState([])
  const [current, setCurrent] = useState(null) // WikiDetail
  const [loading, setLoading] = useState(true)
  const [msg, setMsg] = useState('')

  // 페이지 뷰어/에디터
  const [selectedPage, setSelectedPage] = useState(null) // PageDetail
  const [editing, setEditing] = useState(false)
  const [draftTitle, setDraftTitle] = useState('')
  const [draftContent, setDraftContent] = useState('')

  // 신규 위키
  const [newWiki, setNewWiki] = useState(null)

  // 카테고리 추가
  const [newCatName, setNewCatName] = useState('')

  // 주입 다이얼로그
  const [ingestOpen, setIngestOpen] = useState(false)

  // 채팅
  const [messages, setMessages] = useState([])
  const [chatInput, setChatInput] = useState('')
  const [streaming, setStreaming] = useState(false)
  const [liveSources, setLiveSources] = useState(null)
  const [liveAnswer, setLiveAnswer] = useState('')
  const [liveSearching, setLiveSearching] = useState(null)
  const chatScrollRef = useRef(null)
  const chatAbortRef = useRef(null)

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const [m, w] = await Promise.all([
        api.llmwiki.listModels(),
        api.llmwiki.listWikis(),
      ])
      setModels(m)
      setWikis(w)
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
    return () => {
      if (chatAbortRef.current) chatAbortRef.current.abort()
    }
  }, [])

  useEffect(() => {
    if (chatScrollRef.current) {
      chatScrollRef.current.scrollTop = chatScrollRef.current.scrollHeight
    }
  }, [messages, liveAnswer])

  async function selectWiki(id) {
    setMsg('')
    setEditing(false)
    setSelectedPage(null)
    try {
      const detail = await api.llmwiki.getWiki(id)
      setCurrent(detail)
      setMessages(await api.llmwiki.listMessages(id))
    } catch (err) {
      setMsg(err instanceof ApiError ? err.message : '위키 로드에 실패했습니다')
    }
  }

  async function handleCreateWiki() {
    if (!newWiki?.title?.trim()) {
      setMsg('위키 이름을 입력하세요')
      return
    }
    try {
      const w = await api.llmwiki.createWiki({
        title: newWiki.title.trim(),
        provider_id: newWiki.provider_id || null,
        model: newWiki.model || null,
      })
      setNewWiki(null)
      await load()
      await selectWiki(w.id)
    } catch (err) {
      setMsg(err instanceof ApiError ? err.message : '위키 생성에 실패했습니다')
    }
  }

  async function handleDeleteWiki(id, e) {
    e.stopPropagation()
    if (!window.confirm('이 위키와 모든 페이지를 삭제하시겠습니까?')) return
    try {
      await api.llmwiki.deleteWiki(id)
      if (current?.id === id) {
        setCurrent(null)
        setSelectedPage(null)
        setMessages([])
      }
      load()
    } catch (err) {
      setMsg(err instanceof ApiError ? err.message : '삭제에 실패했습니다')
    }
  }

  // ── 카테고리 ──────────────────────────────────────────────
  async function handleAddCategory(e) {
    e.preventDefault()
    if (!newCatName.trim() || !current) return
    try {
      const cat = await api.llmwiki.createCategory(current.id, newCatName.trim())
      setNewCatName('')
      setCurrent({ ...current, tree: { ...current.tree, categories: [...current.tree.categories, cat] } })
    } catch (err) {
      setMsg(err instanceof ApiError ? err.message : '카테고리 생성 실패')
    }
  }

  async function handleRenameCategory(cat, e) {
    e.stopPropagation()
    const name = window.prompt('카테고리 이름', cat.name)
    if (!name || name === cat.name) return
    try {
      const updated = await api.llmwiki.updateCategory(current.id, cat.id, name)
      setCurrent({
        ...current,
        tree: {
          ...current.tree,
          categories: current.tree.categories.map((c) => (c.id === cat.id ? updated : c)),
        },
      })
    } catch (err) {
      setMsg(err instanceof ApiError ? err.message : '이름 변경 실패')
    }
  }

  async function handleDeleteCategory(cat, e) {
    e.stopPropagation()
    if (!window.confirm(`'${cat.name}' 카테고리와 하위 페이지를 삭제하시겠습니까?`)) return
    try {
      await api.llmwiki.deleteCategory(current.id, cat.id)
      await selectWiki(current.id)
    } catch (err) {
      setMsg(err instanceof ApiError ? err.message : '삭제 실패')
    }
  }

  // ── 페이지 ────────────────────────────────────────────────
  async function selectPage(pageId) {
    setMsg('')
    setEditing(false)
    try {
      const p = await api.llmwiki.getPage(current.id, pageId)
      setSelectedPage(p)
      setDraftTitle(p.title)
      setDraftContent(p.content)
    } catch (err) {
      setMsg(err instanceof ApiError ? err.message : '페이지 로드 실패')
    }
  }

  async function handleCreatePage(categoryId) {
    try {
      const p = await api.llmwiki.createPage(current.id, {
        category_id: categoryId || null,
        title: '새 페이지',
        content: '# 새 페이지\n\n',
      })
      await selectWiki(current.id)
      await selectPage(p.id)
      setEditing(true)
    } catch (err) {
      setMsg(err instanceof ApiError ? err.message : '페이지 생성 실패')
    }
  }

  async function handleSavePage() {
    try {
      const p = await api.llmwiki.updatePage(current.id, selectedPage.id, {
        title: draftTitle.trim() || selectedPage.title,
        content: draftContent,
      })
      setSelectedPage(p)
      setEditing(false)
      await selectWiki(current.id)
      await selectPage(p.id)
    } catch (err) {
      setMsg(err instanceof ApiError ? err.message : '저장 실패')
    }
  }

  async function handleDeletePage(pageId, e) {
    e.stopPropagation()
    if (!window.confirm('이 페이지를 삭제하시겠습니까?')) return
    try {
      await api.llmwiki.deletePage(current.id, pageId)
      if (selectedPage?.id === pageId) setSelectedPage(null)
      await selectWiki(current.id)
    } catch (err) {
      setMsg(err instanceof ApiError ? err.message : '삭제 실패')
    }
  }

  // ── 주입 ──────────────────────────────────────────────────
  async function handleIngest(form) {
    try {
      const res = await api.llmwiki.ingest(current.id, form)
      setIngestOpen(false)
      let msg =
        res.created_pages.length > 0
          ? `${res.created_pages.length}개 페이지를 추가했습니다`
          : ''
      if (res.auto_categorized) {
        const newCats = (res.created_categories || []).length
        const names = (res.created_categories || []).map((c) => c.name).join(', ')
        msg += newCats > 0 ? ` · 자동 분류 (새 카테고리: ${names})` : ' · 자동 분류'
      }
      setMsg(msg)
      await selectWiki(current.id)
    } catch (err) {
      setMsg(err instanceof ApiError ? err.message : '주입에 실패했습니다')
    }
  }

  // ── 채팅 ──────────────────────────────────────────────────
  async function handleChat(e) {
    e.preventDefault()
    if (!chatInput.trim() || !current || streaming) return
    const question = chatInput.trim()
    setChatInput('')
    setStreaming(true)
    setLiveSources(null)
    setLiveAnswer('')
    setLiveSearching(null)

    // 낙관적 사용자 메시지
    const tempUser = { id: `u-${Date.now()}`, role: 'user', content: question, sources: null }
    setMessages((prev) => [...prev, tempUser])

    const ctrl = new AbortController()
    chatAbortRef.current = ctrl
    let assistantId = `a-${Date.now()}`
    let sources = null
    let answer = ''
    try {
      await api.llmwiki.chat(
        current.id,
        question,
        ({ event, data }) => {
          if (event === 'sources') {
            sources = data.sources
            setLiveSources({ sources: data.sources, is_web_fallback: data.is_web_fallback })
          } else if (event === 'searching') {
            setLiveSearching({ query: data.query, iteration: data.iteration })
            setLiveAnswer('')
          } else if (event === 'delta') {
            setLiveSearching(null)
            answer += data.delta
            setLiveAnswer(answer)
          } else if (event === 'done') {
            if (data.saving_in_background) {
              setMsg('웹 검색 결과를 백그라운드에서 위키에 저장하는 중…')
            }
          } else if (event === 'error') {
            setMsg(data.message)
          }
        },
        ctrl.signal
      )
    } catch (err) {
      if (err?.name !== 'AbortError') {
        setMsg(err instanceof ApiError ? err.message : '채팅에 실패했습니다')
      }
    }
    // 실제 이력으로 교체
    setLiveSources(null)
    setLiveAnswer('')
    setLiveSearching(null)
    setMessages((prev) => [
      ...prev.filter((m) => m.id !== tempUser.id),
      { id: `u-${Date.now()}`, role: 'user', content: question, sources: null },
      { id: assistantId, role: 'assistant', content: answer, sources },
    ])
    setStreaming(false)
  }

  async function handleClearChat() {
    if (!current) return
    if (streaming && chatAbortRef.current) chatAbortRef.current.abort()
    if (!window.confirm('이 위키의 채팅 기록을 모두 삭제합니다')) return
    try {
      await api.llmwiki.clearMessages(current.id)
      setMessages([])
      setLiveSources(null)
      setLiveAnswer('')
      setLiveSearching(null)
      setStreaming(false)
      setMsg('채팅을 초기화했습니다')
    } catch (err) {
      setMsg(err instanceof ApiError ? err.message : '채팅 초기화에 실패했습니다')
    }
  }

  function openSource(src) {
    if (src.type === 'wiki' && src.ref) {
      selectPage(src.ref)
    } else if (src.type === 'web' && src.ref) {
      window.open(src.ref, '_blank', 'noopener')
    }
  }

  function renderSources(sources) {
    if (!sources || sources.length === 0) return null
    return (
      <div className="mt-2 flex flex-wrap gap-1">
        {sources.map((s, i) => (
          <button
            key={i}
            onClick={() => openSource(s)}
            className={`rounded px-1.5 py-0.5 text-[10px] ${
              s.type === 'wiki'
                ? 'bg-primary/10 text-primary hover:bg-primary/20'
                : 'bg-muted text-muted-foreground hover:bg-foreground/10'
            }`}
            title={s.ref}
          >
            {s.type === 'wiki' ? '📄' : '🌐'} {s.title}
          </button>
        ))}
      </div>
    )
  }

  // 트리 그룹화: 카테고리별 + 미분류
  const tree = current?.tree
  const pagesByCat = {}
  const uncategorized = []
  for (const p of tree?.pages || []) {
    if (p.category_id) {
      ;(pagesByCat[p.category_id] ||= []).push(p)
    } else {
      uncategorized.push(p)
    }
  }

  const selectedProvider = models.providers.find((p) => p.id === newWiki?.provider_id)

  return (
    <div className="flex h-full flex-col">
      <div className="flex items-center justify-between">
        <h1 className="flex items-center gap-2 text-2xl font-semibold">
          <BookOpen size={22} /> LLM 위키
        </h1>
        {current && canCreate && (
          <div className="flex gap-1">
            <Button size="sm" variant="outline" onClick={() => setIngestOpen(true)}>
              <Upload size={14} /> 자료 주입
            </Button>
          </div>
        )}
      </div>

      {msg && <p className="mt-2 text-xs text-destructive">{msg}</p>}

      <PanelGroup orientation="horizontal" className="mt-4 flex-1 overflow-hidden">
        {/* 좌: 워크스페이스 + 트리 */}
        <Panel id="wiki-tree" defaultSize={260} minSize={200} maxSize={420} className="overflow-auto pr-2">
          {canCreate && (
            <Button
              size="sm"
              className="w-full"
              onClick={() => {
                setCurrent(null)
                setNewWiki({ title: '', provider_id: '', model: '' })
              }}
            >
              <Plus size={14} /> 새 위키
            </Button>
          )}
          <div className="mt-3 space-y-1">
            {wikis.map((w) => (
              <div
                key={w.id}
                className={`group flex items-center rounded transition-colors ${
                  current?.id === w.id ? 'bg-accent text-accent-foreground' : 'hover:bg-accent/50'
                }`}
              >
                <button
                  onClick={() => selectWiki(w.id)}
                  className="flex-1 truncate px-2 py-1.5 text-left text-xs"
                >
                  {w.title}
                  {w.model && (
                    <span className="ml-1 text-[10px] text-muted-foreground">{w.model}</span>
                  )}
                </button>
                {canDelete && (
                  <button
                    onClick={(e) => handleDeleteWiki(w.id, e)}
                    className="mr-1 shrink-0 rounded p-1 text-muted-foreground opacity-0 transition-opacity hover:text-destructive group-hover:opacity-100"
                    title="삭제"
                  >
                    <Trash2 size={12} />
                  </button>
                )}
              </div>
            ))}
          </div>

          {tree && (
            <div className="mt-4 border-t pt-3">
              <form onSubmit={handleAddCategory} className="flex gap-1">
                <Input
                  value={newCatName}
                  onChange={(e) => setNewCatName(e.target.value)}
                  placeholder="카테고리"
                  className="text-xs"
                />
                {canCreate && (
                  <Button size="icon-sm" type="submit" variant="outline" disabled={!newCatName.trim()}>
                    <FolderPlus size={14} />
                  </Button>
                )}
              </form>

              <div className="mt-2 space-y-0.5">
                {tree.categories.map((cat) => (
                  <CategoryNode
                    key={cat.id}
                    cat={cat}
                    pages={pagesByCat[cat.id] || []}
                    selectedPageId={selectedPage?.id}
                    canUpdate={canUpdate}
                    canDelete={canDelete}
                    canCreate={canCreate}
                    onSelectPage={selectPage}
                    onAddPage={handleCreatePage}
                    onRename={() => handleRenameCategory(cat, { stopPropagation: () => {} })}
                    onDelete={(e) => handleDeleteCategory(cat, e)}
                    onDeletePage={handleDeletePage}
                  />
                ))}
                {/* 미분류 */}
                <div className="mt-1">
                  <div className="flex items-center justify-between rounded px-1 py-1">
                    <span className="text-[11px] font-medium text-muted-foreground">미분류</span>
                    {canCreate && (
                      <button
                        onClick={() => handleCreatePage(null)}
                        className="rounded p-0.5 text-muted-foreground hover:text-foreground"
                        title="페이지 추가"
                      >
                        <FilePlus size={12} />
                      </button>
                    )}
                  </div>
                  {uncategorized.map((p) => (
                    <PageNode
                      key={p.id}
                      page={p}
                      selected={selectedPage?.id === p.id}
                      canDelete={canDelete}
                      onSelect={() => selectPage(p.id)}
                      onDelete={(e) => handleDeletePage(p.id, e)}
                    />
                  ))}
                </div>
              </div>
            </div>
          )}
        </Panel>

        <PanelSeparator className="w-1.5 shrink-0 bg-border transition-colors hover:bg-primary/50 data-[separator=active]:bg-primary" />

        {/* 중: 페이지 뷰어/에디터 */}
        <Panel id="wiki-page" className="flex flex-col overflow-hidden">
          {!selectedPage ? (
            <div className="flex flex-1 items-center justify-center text-sm text-muted-foreground">
              {current ? '페이지를 선택하거나 주입하세요' : '위키를 선택하거나 새로 만드세요'}
            </div>
          ) : editing ? (
            <div className="flex h-full flex-col gap-2">
              <div className="flex items-center gap-2">
                <Input
                  value={draftTitle}
                  onChange={(e) => setDraftTitle(e.target.value)}
                  className="text-sm"
                  placeholder="페이지 제목"
                />
                <Button size="sm" onClick={handleSavePage} disabled={!canUpdate}>
                  저장
                </Button>
                <Button size="sm" variant="outline" onClick={() => setEditing(false)}>
                  취소
                </Button>
              </div>
              <textarea
                value={draftContent}
                onChange={(e) => setDraftContent(e.target.value)}
                className="flex-1 resize-none rounded-md border bg-background p-3 font-mono text-xs"
              />
            </div>
          ) : (
            <div className="flex h-full flex-col">
              <div className="mb-2 flex items-center gap-2">
                <h2 className="flex-1 truncate text-base font-medium">{selectedPage.title}</h2>
                <span className="rounded bg-muted px-1.5 py-0.5 text-[10px] text-muted-foreground">
                  {SOURCE_LABEL[selectedPage.source_type] || selectedPage.source_type}
                </span>
                {canUpdate && (
                  <Button size="xs" variant="outline" onClick={() => setEditing(true)}>
                    <Pencil size={11} /> 수정
                  </Button>
                )}
              </div>
              <div className="flex-1 overflow-auto">
                <MarkdownRenderer>{selectedPage.content}</MarkdownRenderer>
              </div>
            </div>
          )}
        </Panel>

        <PanelSeparator className="w-1.5 shrink-0 bg-border transition-colors hover:bg-primary/50 data-[separator=active]:bg-primary" />

        {/* 우: 채팅 */}
        <Panel id="wiki-chat" defaultSize={380} minSize={280} className="flex flex-col overflow-hidden">
          {!current ? (
            <div className="flex flex-1 items-center justify-center text-sm text-muted-foreground">
              채팅은 위키 선택 후 가능합니다
            </div>
          ) : !current.model ? (
            <div className="flex flex-1 items-center justify-center px-4 text-center text-xs text-muted-foreground">
              채팅·주입에 사용할 LLM 모델이 설정되지 않았습니다. 새 위키 생성 시 제공자/모델을 지정하세요.
            </div>
          ) : (
            <>
              <div className="flex items-center justify-between border-b pb-2">
                <span className="text-xs font-medium text-muted-foreground">채팅</span>
                <button
                  type="button"
                  onClick={handleClearChat}
                  className="flex items-center gap-1 rounded px-1.5 py-1 text-[11px] text-muted-foreground hover:bg-muted hover:text-destructive"
                  title="채팅 기록 전체 삭제"
                >
                  <Trash2 size={12} />
                  초기화
                </button>
              </div>
              <div ref={chatScrollRef} className="flex-1 space-y-3 overflow-auto pb-2">
                {messages.map((m) => (
                  <div key={m.id}>
                    {m.role === 'user' ? (
                      <div className="flex justify-end">
                        <div className="max-w-[85%] whitespace-pre-wrap rounded-lg bg-primary px-3 py-2 text-xs text-primary-foreground">
                          {m.content}
                        </div>
                      </div>
                    ) : (
                      <div className="rounded-lg border bg-card p-3">
                        <MarkdownRenderer>{m.content}</MarkdownRenderer>
                        {renderSources(m.sources)}
                      </div>
                    )}
                  </div>
                ))}

                {streaming && (
                  <div className="rounded-lg border bg-card p-3">
                    {liveSearching && (
                      <p className="mb-1 flex items-center gap-1 text-[11px] text-amber-600">
                        <span className="inline-block h-2 w-2 animate-pulse rounded-full bg-amber-500" />
                        웹에서 추가 정보 검색 중{liveSearching.iteration > 1 ? ` (${liveSearching.iteration}회차)` : ''}: {liveSearching.query}
                      </p>
                    )}
                    {liveSources && (
                      <>
                        {liveSources.is_web_fallback && (
                          <p className="mb-1 text-[10px] text-amber-600">
                            웹 검색 결과를 포함해 답변합니다.
                          </p>
                        )}
                        {renderSources(liveSources.sources)}
                      </>
                    )}
                    {liveAnswer ? (
                      <MarkdownRenderer>{liveAnswer}</MarkdownRenderer>
                    ) : (
                      !liveSearching && <p className="text-xs text-muted-foreground">생성 중…</p>
                    )}
                  </div>
                )}
              </div>

              <form onSubmit={handleChat} className="flex gap-2 border-t pt-3">
                <Input
                  value={chatInput}
                  onChange={(e) => setChatInput(e.target.value)}
                  placeholder="위키에 질문하세요"
                  disabled={streaming}
                />
                <Button type="submit" size="sm" disabled={!chatInput.trim() || streaming}>
                  전송
                </Button>
              </form>
            </>
          )}
        </Panel>
      </PanelGroup>

      {/* 신규 위키 다이얼로그 */}
      {newWiki && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40">
          <div className="w-full max-w-md space-y-3 rounded-lg border bg-card p-4">
            <div className="flex items-center justify-between">
              <h2 className="text-sm font-medium">새 위키</h2>
              <button onClick={() => setNewWiki(null)} className="text-muted-foreground hover:text-foreground">
                <X size={16} />
              </button>
            </div>
            <label className="block text-xs">
              <span className="mb-1 block text-muted-foreground">위키 이름</span>
              <Input
                value={newWiki.title}
                onChange={(e) => setNewWiki({ ...newWiki, title: e.target.value })}
                placeholder="예: 개인 지식 베이스"
                autoFocus
              />
            </label>
            <label className="block text-xs">
              <span className="mb-1 block text-muted-foreground">제공자(선택)</span>
              <select
                value={newWiki.provider_id}
                onChange={(e) => setNewWiki({ provider_id: e.target.value, model: '', title: newWiki.title })}
                className="w-full rounded-md border bg-background px-3 py-2 text-sm"
              >
                <option value="">선택 안함</option>
                {models.providers.map((p) => (
                  <option key={p.id} value={p.id}>
                    {p.display_name}
                  </option>
                ))}
              </select>
            </label>
            <label className="block text-xs">
              <span className="mb-1 block text-muted-foreground">모델(선택)</span>
              <select
                value={newWiki.model}
                onChange={(e) => setNewWiki({ ...newWiki, model: e.target.value })}
                disabled={!selectedProvider || (selectedProvider?.models || []).length === 0}
                className="w-full rounded-md border bg-background px-3 py-2 text-sm disabled:opacity-60"
              >
                <option value="">선택 안함</option>
                {(selectedProvider?.models || []).map((m) => (
                  <option key={m} value={m}>
                    {m}
                  </option>
                ))}
              </select>
            </label>
            <Button size="sm" className="w-full" onClick={handleCreateWiki} disabled={!newWiki.title.trim()}>
              생성
            </Button>
          </div>
        </div>
      )}

      {/* 주입 다이얼로그 */}
      {ingestOpen && current && (
        <IngestDialog
          wiki={current}
          onClose={() => setIngestOpen(false)}
          onSubmit={handleIngest}
        />
      )}
    </div>
  )
}

function CategoryNode({
  cat,
  pages,
  selectedPageId,
  canUpdate,
  canDelete,
  canCreate,
  onSelectPage,
  onAddPage,
  onRename,
  onDelete,
  onDeletePage,
}) {
  const [open, setOpen] = useState(true)
  return (
    <div>
      <div className="group flex items-center rounded px-1 py-1 hover:bg-accent/40">
        <button onClick={() => setOpen((o) => !o)} className="text-muted-foreground">
          {open ? <ChevronDown size={12} /> : <ChevronRight size={12} />}
        </button>
        <span className="ml-1 flex-1 truncate text-[11px] font-medium">{cat.name}</span>
        {canCreate && (
          <button
            onClick={(e) => {
              e.stopPropagation()
              onAddPage(cat.id)
            }}
            className="mr-0.5 rounded p-0.5 text-muted-foreground opacity-0 hover:text-foreground group-hover:opacity-100"
            title="페이지 추가"
          >
            <FilePlus size={12} />
          </button>
        )}
        {canUpdate && (
          <button
            onClick={onRename}
            className="mr-0.5 rounded p-0.5 text-muted-foreground opacity-0 hover:text-foreground group-hover:opacity-100"
            title="이름 변경"
          >
            <Pencil size={11} />
          </button>
        )}
        {canDelete && (
          <button
            onClick={onDelete}
            className="rounded p-0.5 text-muted-foreground opacity-0 hover:text-destructive group-hover:opacity-100"
            title="삭제"
          >
            <Trash2 size={11} />
          </button>
        )}
      </div>
      {open && (
        <div className="ml-3 border-l pl-2">
          {pages.map((p) => (
            <PageNode
              key={p.id}
              page={p}
              selected={selectedPageId === p.id}
              canDelete={canDelete}
              onSelect={() => onSelectPage(p.id)}
              onDelete={(e) => onDeletePage(p.id, e)}
            />
          ))}
          {pages.length === 0 && (
            <p className="px-1 py-0.5 text-[10px] text-muted-foreground/60">페이지 없음</p>
          )}
        </div>
      )}
    </div>
  )
}

function PageNode({ page, selected, canDelete, onSelect, onDelete }) {
  return (
    <div
      className={`group flex items-center rounded px-1 py-1 text-[11px] ${
        selected ? 'bg-accent text-accent-foreground' : 'hover:bg-accent/50'
      }`}
    >
      <button onClick={onSelect} className="flex-1 truncate text-left">
        <span className="mr-1 text-[9px] text-muted-foreground">{SOURCE_LABEL[page.source_type] || ''}</span>
        {page.title}
      </button>
      {canDelete && (
        <button
          onClick={onDelete}
          className="rounded p-0.5 text-muted-foreground opacity-0 hover:text-destructive group-hover:opacity-100"
          title="삭제"
        >
          <Trash2 size={10} />
        </button>
      )}
    </div>
  )
}

function IngestDialog({ wiki, onClose, onSubmit }) {
  const [files, setFiles] = useState([])
  const [deepResearchSessions, setDeepResearchSessions] = useState([])
  const [sessionId, setSessionId] = useState('')
  const [youtubeUrl, setYoutubeUrl] = useState('')
  const [categoryId, setCategoryId] = useState('')
  const [busy, setBusy] = useState(false)
  const [err, setErr] = useState('')
  const [dragOver, setDragOver] = useState(false)
  const inputRef = useRef(null)

  useEffect(() => {
    api.llmwiki
      .listDeepResearchSessions()
      .then((rows) => {
        const done = rows.filter((s) => s.status === 'completed')
        setDeepResearchSessions(done)
      })
      .catch(() => {})
  }, [])

  function addFiles(list) {
    const arr = Array.from(list || [])
    setFiles((prev) => [...prev, ...arr])
  }

  function submit(e) {
    e.preventDefault()
    if (files.length === 0 && !sessionId && !youtubeUrl) {
      setErr('파일·딥 리서치 세션·YouTube URL 중 하나 이상 필요합니다')
      return
    }
    const form = new FormData()
    for (const f of files) form.append('files', f)
    if (sessionId) form.append('deepresearch_session_id', sessionId)
    if (youtubeUrl) form.append('youtube_url', youtubeUrl)
    if (categoryId === '__auto__') form.append('auto_categorize', 'true')
    else if (categoryId) form.append('category_id', categoryId)
    setBusy(true)
    onSubmit(form)
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40">
      <form onSubmit={submit} className="w-full max-w-lg space-y-3 rounded-lg border bg-card p-4">
        <div className="flex items-center justify-between">
          <h2 className="text-sm font-medium">자료 주입 — {wiki.title}</h2>
          <button type="button" onClick={onClose} className="text-muted-foreground hover:text-foreground">
            <X size={16} />
          </button>
        </div>

        {err && <p className="text-xs text-destructive">{err}</p>}

        {/* 파일 드롭존 */}
        <div
          onDragOver={(e) => {
            e.preventDefault()
            setDragOver(true)
          }}
          onDragLeave={() => setDragOver(false)}
          onDrop={(e) => {
            e.preventDefault()
            setDragOver(false)
            addFiles(e.dataTransfer.files)
          }}
          onClick={() => inputRef.current?.click()}
          className={`cursor-pointer rounded-md border-2 border-dashed p-4 text-center text-xs ${
            dragOver ? 'border-primary bg-primary/5' : 'border-border'
          }`}
        >
          <Upload size={20} className="mx-auto mb-1 text-muted-foreground" />
          <p className="text-muted-foreground">MD · PDF · 이미지를 드롭하거나 클릭하여 선택</p>
          <input
            ref={inputRef}
            type="file"
            multiple
            accept=".md,.pdf,.png,.jpg,.jpeg,.gif,.webp,.bmp,text/markdown,application/pdf,image/*"
            className="hidden"
            onChange={(e) => addFiles(e.target.files)}
          />
          {files.length > 0 && (
            <div className="mt-2 space-y-1">
              {files.map((f, i) => (
                <div key={i} className="flex items-center justify-between rounded bg-muted px-2 py-1">
                  <span className="truncate">{f.name}</span>
                  <button
                    type="button"
                    onClick={(e) => {
                      e.stopPropagation()
                      setFiles(files.filter((_, idx) => idx !== i))
                    }}
                    className="text-muted-foreground hover:text-destructive"
                  >
                    <X size={12} />
                  </button>
                </div>
              ))}
            </div>
          )}
        </div>

        <label className="block text-xs">
          <span className="mb-1 block text-muted-foreground">딥 리서치 결과 세션(선택)</span>
          <select
            value={sessionId}
            onChange={(e) => setSessionId(e.target.value)}
            className="w-full rounded-md border bg-background px-3 py-2 text-sm"
          >
            <option value="">선택 안함</option>
            {deepResearchSessions.map((s) => (
              <option key={s.id} value={s.id}>
                {s.title || s.model}
              </option>
            ))}
          </select>
          {deepResearchSessions.length === 0 && (
            <span className="mt-0.5 block text-[10px] text-muted-foreground">
              완료된 딥 리서치 세션이 없습니다.
            </span>
          )}
        </label>

        <label className="block text-xs">
          <span className="mb-1 block text-muted-foreground">YouTube URL(선택)</span>
          <Input
            value={youtubeUrl}
            onChange={(e) => setYoutubeUrl(e.target.value)}
            placeholder="https://www.youtube.com/watch?v=..."
          />
        </label>

        <label className="block text-xs">
          <span className="mb-1 block text-muted-foreground">저장할 카테고리(선택)</span>
          <select
            value={categoryId}
            onChange={(e) => setCategoryId(e.target.value)}
            className="w-full rounded-md border bg-background px-3 py-2 text-sm"
          >
            <option value="">미분류</option>
            <option value="__auto__">자동 분할 분류 (LLM)</option>
            {wiki.tree.categories.map((c) => (
              <option key={c.id} value={c.id}>
                {c.name}
              </option>
            ))}
          </select>
          {categoryId === '__auto__' && (
            <span className="mt-0.5 block text-[10px] text-muted-foreground">
              각 자료의 내용을 LLM이 주제별로 분해해 여러 페이지/카테고리로 자동 생성합니다.
            </span>
          )}
        </label>

        <Button type="submit" size="sm" className="w-full" disabled={busy}>
          {busy ? '주입 중…' : '주입'}
        </Button>
      </form>
    </div>
  )
}
