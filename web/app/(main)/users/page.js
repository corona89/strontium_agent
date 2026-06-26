'use client'

import { useState, useEffect, useCallback } from 'react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Separator } from '@/components/ui/separator'
import { api, ApiError } from '@/lib/api'
import useAuthStore from '@/store/auth'

export default function UsersPage() {
  const user = useAuthStore((s) => s.user)
  const permissions = user?.permissions || {}
  const canUpdate = permissions.users?.update
  const canDelete = permissions.users?.delete

  const [users, setUsers] = useState([])
  const [total, setTotal] = useState(0)
  const [page, setPage] = useState(1)
  const [roles, setRoles] = useState([])
  const [loading, setLoading] = useState(true)
  const [msg, setMsg] = useState('')
  const [tempPassword, setTempPassword] = useState(null)

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const [userData, roleData] = await Promise.all([
        api.admin.listUsers(page),
        api.roles.list(),
      ])
      setUsers(userData.users)
      setTotal(userData.total)
      setRoles(roleData)
    } catch (err) {
      setMsg(err instanceof ApiError ? err.message : '로드에 실패했습니다')
    } finally {
      setLoading(false)
    }
  }, [page])

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    load()
  }, [load])

  async function handleRoleChange(userId, selectedRoleIds) {
    try {
      await api.admin.updateUserRoles(userId, selectedRoleIds)
      setMsg('역할을 변경했습니다')
      load()
    } catch (err) {
      setMsg(err instanceof ApiError ? err.message : '역할 변경에 실패했습니다')
    }
  }

  async function handleResetPassword(userId) {
    if (!window.confirm('비밀번호를 초기화하시겠습니까?')) return
    try {
      const res = await api.admin.resetUserPassword(userId)
      setTempPassword({ userId, password: res.temporary_password })
      load()
    } catch (err) {
      setMsg(err instanceof ApiError ? err.message : '비밀번호 초기화에 실패했습니다')
    }
  }

  async function handleDeactivate(userId) {
    if (!window.confirm('이 사용자를 비활성화하시겠습니까?')) return
    try {
      await api.admin.deactivateUser(userId)
      setMsg('사용자를 비활성화했습니다')
      load()
    } catch (err) {
      setMsg(err instanceof ApiError ? err.message : '비활성화에 실패했습니다')
    }
  }

  function toggleRole(currentIds, roleId) {
    if (currentIds.includes(roleId)) {
      return currentIds.filter((id) => id !== roleId)
    }
    return [...currentIds, roleId]
  }

  const pageSize = 20
  const totalPages = Math.ceil(total / pageSize)

  return (
    <div>
      <h1 className="text-2xl font-semibold">사용자 관리</h1>
      <p className="mt-1 text-sm text-muted-foreground">총 {total}명</p>

      {msg && <p className="mt-3 text-xs text-muted-foreground">{msg}</p>}

      {loading ? (
        <p className="mt-8 text-sm text-muted-foreground">로딩 중...</p>
      ) : (
        <div className="mt-6 overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b text-left text-xs text-muted-foreground">
                <th className="pb-2 pr-4 font-medium">이메일</th>
                <th className="pb-2 pr-4 font-medium">닉네임</th>
                <th className="pb-2 pr-4 font-medium">역할</th>
                <th className="pb-2 pr-4 font-medium">상태</th>
                {canUpdate && <th className="pb-2 pr-4 font-medium">비밀번호</th>}
                {canDelete && <th className="pb-2 pr-4 font-medium">삭제</th>}
              </tr>
            </thead>
            <tbody>
              {users.map((u) => {
                const userRoleIds = u.roles.map((r) => r.id)
                return (
                  <tr key={u.id} className="border-b">
                    <td className="py-3 pr-4">{u.email}</td>
                    <td className="py-3 pr-4">{u.nickname || '-'}</td>
                    <td className="py-3 pr-4">
                      {canUpdate ? (
                        <div className="flex flex-wrap gap-1">
                          {roles.map((role) => (
                            <button
                              key={role.id}
                              onClick={() =>
                                handleRoleChange(
                                  u.id,
                                  toggleRole(userRoleIds, role.id)
                                )
                              }
                              className={`rounded px-2 py-0.5 text-xs transition-colors ${
                                userRoleIds.includes(role.id)
                                  ? 'bg-primary text-primary-foreground'
                                  : 'bg-muted text-muted-foreground hover:bg-accent'
                              }`}
                            >
                              {role.name}
                            </button>
                          ))}
                        </div>
                      ) : (
                        <span>{u.roles.map((r) => r.name).join(', ') || '-'}</span>
                      )}
                    </td>
                    <td className="py-3 pr-4">
                      <span
                        className={
                          u.is_active ? 'text-primary' : 'text-destructive'
                        }
                      >
                        {u.is_active ? '활성' : '비활성'}
                      </span>
                    </td>
                    {canUpdate && (
                      <td className="py-3 pr-4">
                        <Button
                          size="xs"
                          variant="outline"
                          onClick={() => handleResetPassword(u.id)}
                        >
                          초기화
                        </Button>
                      </td>
                    )}
                    {canDelete && (
                      <td className="py-3 pr-4">
                        <Button
                          size="xs"
                          variant="destructive"
                          onClick={() => handleDeactivate(u.id)}
                          disabled={!u.is_active || u.id === user?.id}
                        >
                          삭제
                        </Button>
                      </td>
                    )}
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      )}

      {totalPages > 1 && (
        <div className="mt-4 flex items-center gap-2">
          <Button
            size="xs"
            variant="outline"
            onClick={() => setPage((p) => Math.max(1, p - 1))}
            disabled={page === 1}
          >
            이전
          </Button>
          <span className="text-xs text-muted-foreground">
            {page} / {totalPages}
          </span>
          <Button
            size="xs"
            variant="outline"
            onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
            disabled={page === totalPages}
          >
            다음
          </Button>
        </div>
      )}

      {tempPassword && (
        <div className="fixed inset-0 flex items-center justify-center bg-black/50" onClick={() => setTempPassword(null)}>
          <div className="rounded-lg bg-card p-6 shadow-lg" onClick={(e) => e.stopPropagation()}>
            <h2 className="text-sm font-medium">임시 비밀번호</h2>
            <p className="mt-2 text-xs text-muted-foreground">
              이 비밀번호는 한 번만 표시됩니다. 사용자에게 전달하세요.
            </p>
            <Input
              readOnly
              value={tempPassword.password}
              className="mt-3 font-mono text-sm"
              onClick={(e) => e.target.select()}
            />
            <div className="mt-4 flex justify-end gap-2">
              <Button
                size="sm"
                variant="outline"
                onClick={() => {
                  navigator.clipboard.writeText(tempPassword.password)
                }}
              >
                복사
              </Button>
              <Button size="sm" onClick={() => setTempPassword(null)}>
                닫기
              </Button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
