'use client'

import { useState } from 'react'
import { useRouter } from 'next/navigation'
import Link from 'next/link'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import SrLogo from '@/components/login/SrLogo'
import { api, ApiError } from '@/lib/api'
import useAuthStore from '@/store/auth'

export default function RegisterPage() {
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [passwordConfirm, setPasswordConfirm] = useState('')
  const [nickname, setNickname] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)
  const setUser = useAuthStore((s) => s.setUser)
  const router = useRouter()

  async function handleRegister(e) {
    e.preventDefault()
    setError('')

    if (password !== passwordConfirm) {
      setError('비밀번호가 일치하지 않습니다')
      return
    }

    setLoading(true)
    try {
      await api.accounts.create(email, password, nickname || undefined)
      await api.auth.login(email, password)
      const user = await api.auth.me()
      setUser(user)
      router.push('/')
    } catch (err) {
      setError(err instanceof ApiError ? err.message : '회원가입에 실패했습니다')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-background px-4">
      <div className="w-full max-w-sm">
        {/* 로고 */}
        <div className="mb-8 flex flex-col items-center gap-3">
          <SrLogo className="size-24" />
          <div className="text-center">
            <h1 className="text-xl font-bold tracking-tight">Where Winds Meet</h1>
            <p className="mt-1 text-xs text-muted-foreground">새 계정을 만드세요</p>
          </div>
        </div>

        {/* 회원가입 폼 */}
        <form onSubmit={handleRegister} className="flex flex-col gap-3">
          <div className="flex flex-col gap-1.5">
            <label htmlFor="email" className="text-xs font-medium">
              이메일
            </label>
            <Input
              id="email"
              type="email"
              placeholder="name@example.com"
              autoComplete="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
            />
          </div>

          <div className="flex flex-col gap-1.5">
            <label htmlFor="password" className="text-xs font-medium">
              비밀번호
            </label>
            <Input
              id="password"
              type="password"
              placeholder="••••••••"
              autoComplete="new-password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
              minLength={8}
            />
          </div>

          <div className="flex flex-col gap-1.5">
            <label htmlFor="password-confirm" className="text-xs font-medium">
              비밀번호 확인
            </label>
            <Input
              id="password-confirm"
              type="password"
              placeholder="••••••••"
              autoComplete="new-password"
              value={passwordConfirm}
              onChange={(e) => setPasswordConfirm(e.target.value)}
              required
              minLength={8}
            />
          </div>

          <div className="flex flex-col gap-1.5">
            <label htmlFor="nickname" className="text-xs font-medium">
              닉네임 (선택)
            </label>
            <Input
              id="nickname"
              type="text"
              placeholder="표시할 이름"
              autoComplete="nickname"
              value={nickname}
              onChange={(e) => setNickname(e.target.value)}
            />
          </div>

          {error && (
            <p className="text-xs text-destructive">{error}</p>
          )}

          <Button type="submit" size="lg" className="mt-1 w-full" disabled={loading}>
            {loading ? '가입 중...' : '회원가입'}
          </Button>
        </form>

        {/* 로그인 링크 */}
        <p className="mt-4 text-center text-xs text-muted-foreground">
          이미 계정이 있으신가요?{' '}
          <Link href="/login" className="font-medium text-foreground hover:underline">
            로그인
          </Link>
        </p>
      </div>
    </div>
  )
}
