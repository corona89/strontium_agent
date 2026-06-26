'use client'

import { useState, useEffect, useCallback } from 'react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { api, ApiError } from '@/lib/api'
import useAuthStore from '@/store/auth'

export default function RolesPage() {
  const user = useAuthStore((s) => s.user)
  const permissions = user?.permissions || {}
  const canCreate = permissions.roles?.create
  const canUpdate = permissions.roles?.update
  const canDelete = permissions.roles?.delete

  const [tab, setTab] = useState('roles')
  const [roles, setRoles] = useState([])
  const [functions, setFunctions] = useState([])
  const [loading, setLoading] = useState(true)
  const [msg, setMsg] = useState('')

  // 역할 편집 상태
  const [editingRole, setEditingRole] = useState(null)
  const [newRoleName, setNewRoleName] = useState('')
  const [newRoleDesc, setNewRoleDesc] = useState('')

  // 기능 편집 상태
  const [newFuncName, setNewFuncName] = useState('')
  const [newFuncDesc, setNewFuncDesc] = useState('')

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const [roleData, funcData] = await Promise.all([
        api.roles.list(),
        api.functions.list(),
      ])
      setRoles(roleData)
      setFunctions(funcData)
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

  async function handleCreateRole() {
    if (!newRoleName.trim()) return
    try {
      await api.roles.create(newRoleName, newRoleDesc || undefined)
      setNewRoleName('')
      setNewRoleDesc('')
      setMsg('역할을 생성했습니다')
      load()
    } catch (err) {
      setMsg(err instanceof ApiError ? err.message : '생성에 실패했습니다')
    }
  }

  async function handleDeleteRole(roleId) {
    if (!window.confirm('이 역할을 삭제하시겠습니까?')) return
    try {
      await api.roles.remove(roleId)
      setMsg('역할을 삭제했습니다')
      load()
    } catch (err) {
      setMsg(err instanceof ApiError ? err.message : '삭제에 실패했습니다')
    }
  }

  async function handleSavePermissions(role) {
    try {
      const entries = (editingRole?.[role.id] || role.functions).map((f) => ({
        function_id: f.function_id,
        can_create: f.can_create,
        can_read: f.can_read,
        can_update: f.can_update,
        can_delete: f.can_delete,
      }))
      await api.roles.setFunctions(role.id, entries)
      setMsg('권한을 저장했습니다')
      load()
    } catch (err) {
      setMsg(err instanceof ApiError ? err.message : '저장에 실패했습니다')
    }
  }

  function togglePerm(roleId, funcId, field) {
    setEditingRole((prev) => {
      const roleData = prev?.[roleId] || roles.find((r) => r.id === roleId)?.functions || []
      const updated = roleData.map((f) =>
        f.function_id === funcId ? { ...f, [field]: !f[field] } : f
      )
      return { ...prev, [roleId]: updated }
    })
  }

  async function handleCreateFunction() {
    if (!newFuncName.trim()) return
    try {
      await api.functions.create(newFuncName, newFuncDesc || undefined)
      setNewFuncName('')
      setNewFuncDesc('')
      setMsg('기능을 생성했습니다')
      load()
    } catch (err) {
      setMsg(err instanceof ApiError ? err.message : '생성에 실패했습니다')
    }
  }

  async function handleDeleteFunction(funcId) {
    if (!window.confirm('이 기능을 삭제하시겠습니까?')) return
    try {
      await api.functions.remove(funcId)
      setMsg('기능을 삭제했습니다')
      load()
    } catch (err) {
      setMsg(err instanceof ApiError ? err.message : '삭제에 실패했습니다')
    }
  }

  if (loading) {
    return <p className="text-sm text-muted-foreground">로딩 중...</p>
  }

  return (
    <div>
      <h1 className="text-2xl font-semibold">역할 및 권한 관리</h1>
      {msg && <p className="mt-3 text-xs text-muted-foreground">{msg}</p>}

      {/* 탭 */}
      <div className="mt-4 flex gap-2 border-b">
        <button
          onClick={() => setTab('roles')}
          className={`px-3 py-2 text-sm transition-colors ${
            tab === 'roles'
              ? 'border-b-2 border-primary font-medium'
              : 'text-muted-foreground hover:text-foreground'
          }`}
        >
          역할
        </button>
        <button
          onClick={() => setTab('functions')}
          className={`px-3 py-2 text-sm transition-colors ${
            tab === 'functions'
              ? 'border-b-2 border-primary font-medium'
              : 'text-muted-foreground hover:text-foreground'
          }`}
        >
          기능
        </button>
      </div>

      {tab === 'roles' && (
        <div className="mt-6">
          {/* 역할 생성 */}
          {canCreate && (
            <div className="mb-6 flex items-end gap-2 rounded-lg border bg-card p-4">
              <div className="flex flex-1 flex-col gap-1">
                <label className="text-xs font-medium">역할명</label>
                <Input
                  value={newRoleName}
                  onChange={(e) => setNewRoleName(e.target.value)}
                  placeholder="새 역할 이름"
                />
              </div>
              <div className="flex flex-1 flex-col gap-1">
                <label className="text-xs font-medium">설명</label>
                <Input
                  value={newRoleDesc}
                  onChange={(e) => setNewRoleDesc(e.target.value)}
                  placeholder="설명 (선택)"
                />
              </div>
              <Button onClick={handleCreateRole}>추가</Button>
            </div>
          )}

          {/* 역할 목록 + 권한 매트릭스 */}
          <div className="space-y-4">
            {roles.map((role) => {
              const roleFunctions = editingRole?.[role.id] || role.functions
              return (
                <div key={role.id} className="rounded-lg border bg-card p-4">
                  <div className="flex items-center justify-between">
                    <div>
                      <span className="font-medium">{role.name}</span>
                      {role.is_system && (
                        <span className="ml-2 rounded bg-muted px-1.5 py-0.5 text-[10px] text-muted-foreground">
                          시스템
                        </span>
                      )}
                      {role.description && (
                        <span className="ml-2 text-xs text-muted-foreground">
                          {role.description}
                        </span>
                      )}
                    </div>
                    <div className="flex gap-2">
                      {canUpdate && (
                        <Button
                          size="xs"
                          variant="outline"
                          onClick={() => handleSavePermissions(role)}
                        >
                          권한 저장
                        </Button>
                      )}
                      {canDelete && !role.is_system && (
                        <Button
                          size="xs"
                          variant="destructive"
                          onClick={() => handleDeleteRole(role.id)}
                        >
                          삭제
                        </Button>
                      )}
                    </div>
                  </div>

                  {/* Function × CRUD 매트릭스 */}
                  <div className="mt-4 overflow-x-auto">
                    <table className="w-full text-xs">
                      <thead>
                        <tr className="border-b text-left text-muted-foreground">
                          <th className="pb-2 pr-4 font-medium">기능</th>
                          <th className="pb-2 px-2 font-medium text-center">C</th>
                          <th className="pb-2 px-2 font-medium text-center">R</th>
                          <th className="pb-2 px-2 font-medium text-center">U</th>
                          <th className="pb-2 px-2 font-medium text-center">D</th>
                        </tr>
                      </thead>
                      <tbody>
                        {functions.map((fn) => {
                          const mapping = roleFunctions.find(
                            (f) => f.function_id === fn.id
                          ) || {
                            function_id: fn.id,
                            can_create: false,
                            can_read: false,
                            can_update: false,
                            can_delete: false,
                          }
                          return (
                            <tr key={fn.id} className="border-b">
                              <td className="py-2 pr-4">{fn.name}</td>
                              {['can_create', 'can_read', 'can_update', 'can_delete'].map(
                                (field) => (
                                  <td key={field} className="py-2 px-2 text-center">
                                    <input
                                      type="checkbox"
                                      checked={mapping[field]}
                                      disabled={!canUpdate}
                                      onChange={() => togglePerm(role.id, fn.id, field)}
                                      className="size-4"
                                    />
                                  </td>
                                )
                              )}
                            </tr>
                          )
                        })}
                      </tbody>
                    </table>
                  </div>
                </div>
              )
            })}
          </div>
        </div>
      )}

      {tab === 'functions' && (
        <div className="mt-6">
          {/* 기능 생성 */}
          {canCreate && (
            <div className="mb-6 flex items-end gap-2 rounded-lg border bg-card p-4">
              <div className="flex flex-1 flex-col gap-1">
                <label className="text-xs font-medium">기능명</label>
                <Input
                  value={newFuncName}
                  onChange={(e) => setNewFuncName(e.target.value)}
                  placeholder="새 기능 이름"
                />
              </div>
              <div className="flex flex-1 flex-col gap-1">
                <label className="text-xs font-medium">설명</label>
                <Input
                  value={newFuncDesc}
                  onChange={(e) => setNewFuncDesc(e.target.value)}
                  placeholder="설명 (선택)"
                />
              </div>
              <Button onClick={handleCreateFunction}>추가</Button>
            </div>
          )}

          {/* 기능 목록 */}
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b text-left text-xs text-muted-foreground">
                  <th className="pb-2 pr-4 font-medium">기능명</th>
                  <th className="pb-2 pr-4 font-medium">설명</th>
                  {canDelete && <th className="pb-2 pr-4 font-medium">삭제</th>}
                </tr>
              </thead>
              <tbody>
                {functions.map((fn) => (
                  <tr key={fn.id} className="border-b">
                    <td className="py-3 pr-4 font-mono">{fn.name}</td>
                    <td className="py-3 pr-4 text-muted-foreground">
                      {fn.description || '-'}
                    </td>
                    {canDelete && (
                      <td className="py-3 pr-4">
                        <Button
                          size="xs"
                          variant="destructive"
                          onClick={() => handleDeleteFunction(fn.id)}
                        >
                          삭제
                        </Button>
                      </td>
                    )}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  )
}
