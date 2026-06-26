'use client'

import { useState } from 'react'
import { useRouter } from 'next/navigation'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Separator } from '@/components/ui/separator'
import { api, ApiError } from '@/lib/api'
import useAuthStore from '@/store/auth'

export default function SettingsPage() {
  const user = useAuthStore((s) => s.user)
  const setUser = useAuthStore((s) => s.setUser)
  const clearUser = useAuthStore((s) => s.clearUser)
  const router = useRouter()

  const [nickname, setNickname] = useState(user?.nickname || '')
  const [nicknameMsg, setNicknameMsg] = useState('')
  const [nicknameLoading, setNicknameLoading] = useState(false)

  const [newPassword, setNewPassword] = useState('')
  const [passwordConfirm, setPasswordConfirm] = useState('')
  const [passwordMsg, setPasswordMsg] = useState('')
  const [passwordLoading, setPasswordLoading] = useState(false)

  const [deactivateLoading, setDeactivateLoading] = useState(false)

  async function handleNicknameSave(e) {
    e.preventDefault()
    setNicknameMsg('')
    setNicknameLoading(true)
    try {
      await api.accounts.update(user.id, { nickname })
      const updated = await api.auth.me()
      setUser(updated)
      setNicknameMsg('닉네임을 저장했습니다')
    } catch (err) {
      setNicknameMsg(err instanceof ApiError ? err.message : '저장에 실패했습니다')
    } finally {
      setNicknameLoading(false)
    }
  }

  async function handlePasswordChange(e) {
    e.preventDefault()
    setPasswordMsg('')
    if (newPassword !== passwordConfirm) {
      setPasswordMsg('비밀번호가 일치하지 않습니다')
      return
    }
    setPasswordLoading(true)
    try {
      await api.accounts.update(user.id, { password: newPassword })
      setNewPassword('')
      setPasswordConfirm('')
      setPasswordMsg('비밀번호를 변경했습니다')
    } catch (err) {
      setPasswordMsg(err instanceof ApiError ? err.message : '변경에 실패했습니다')
    } finally {
      setPasswordLoading(false)
    }
  }

  async function handleDeactivate() {
    if (!window.confirm('정말 계정을 비활성화하시겠습니까? 이 작업은 되돌릴 수 없습니다.')) return
    setDeactivateLoading(true)
    try {
      await api.accounts.deactivate(user.id)
      await api.auth.logout().catch(() => {})
      clearUser()
      router.push('/login')
    } catch (err) {
      setPasswordMsg(err instanceof ApiError ? err.message : '비활성화에 실패했습니다')
    } finally {
      setDeactivateLoading(false)
    }
  }

  if (!user) return null

  return (
    <div className="mx-auto max-w-2xl">
      <h1 className="text-2xl font-semibold">설정</h1>
      <p className="mt-1 text-sm text-muted-foreground">계정 정보를 관리합니다</p>

      {/* 계정 정보 */}
      <section className="mt-8">
        <h2 className="text-sm font-medium text-muted-foreground">계정 정보</h2>
        <dl className="mt-3 flex flex-col gap-2 text-sm">
          <div className="flex justify-between">
            <dt className="text-muted-foreground">이메일</dt>
            <dd>{user.email}</dd>
          </div>
          <div className="flex justify-between">
            <dt className="text-muted-foreground">가입일</dt>
            <dd>{new Date(user.created_at).toLocaleDateString('ko-KR')}</dd>
          </div>
        </dl>
      </section>

      <Separator className="my-6" />

      {/* 닉네임 변경 */}
      <section>
        <h2 className="text-sm font-medium text-muted-foreground">닉네임</h2>
        <form onSubmit={handleNicknameSave} className="mt-3 flex items-end gap-3">
          <div className="flex flex-1 flex-col gap-1.5">
            <Input
              type="text"
              placeholder="표시할 이름"
              value={nickname}
              onChange={(e) => setNickname(e.target.value)}
            />
          </div>
          <Button type="submit" disabled={nicknameLoading}>
            {nicknameLoading ? '저장 중...' : '저장'}
          </Button>
        </form>
        {nicknameMsg && (
          <p className="mt-2 text-xs text-muted-foreground">{nicknameMsg}</p>
        )}
      </section>

      <Separator className="my-6" />

      {/* 비밀번호 변경 */}
      <section>
        <h2 className="text-sm font-medium text-muted-foreground">비밀번호 변경</h2>
        <form onSubmit={handlePasswordChange} className="mt-3 flex flex-col gap-3">
          <div className="flex flex-col gap-1.5">
            <label htmlFor="new-password" className="text-xs font-medium">
              새 비밀번호
            </label>
            <Input
              id="new-password"
              type="password"
              placeholder="••••••••"
              autoComplete="new-password"
              value={newPassword}
              onChange={(e) => setNewPassword(e.target.value)}
              required
              minLength={8}
            />
          </div>
          <div className="flex flex-col gap-1.5">
            <label htmlFor="password-confirm2" className="text-xs font-medium">
              비밀번호 확인
            </label>
            <Input
              id="password-confirm2"
              type="password"
              placeholder="••••••••"
              autoComplete="new-password"
              value={passwordConfirm}
              onChange={(e) => setPasswordConfirm(e.target.value)}
              required
              minLength={8}
            />
          </div>
          {passwordMsg && (
            <p className="text-xs text-muted-foreground">{passwordMsg}</p>
          )}
          <Button type="submit" className="w-fit" disabled={passwordLoading}>
            {passwordLoading ? '변경 중...' : '비밀번호 변경'}
          </Button>
        </form>
      </section>

      <Separator className="my-6" />

      {/* 계정 비활성화 */}
      <section>
        <h2 className="text-sm font-medium text-destructive">계정 비활성화</h2>
        <p className="mt-2 text-xs text-muted-foreground">
          계정을 비활성화하면 더 이상 로그인할 수 없습니다. 이 작업은 되돌릴 수 없습니다.
        </p>
        <Button
          variant="destructive"
          className="mt-3"
          onClick={handleDeactivate}
          disabled={deactivateLoading}
        >
          {deactivateLoading ? '처리 중...' : '계정 비활성화'}
        </Button>
      </section>
    </div>
  )
}
