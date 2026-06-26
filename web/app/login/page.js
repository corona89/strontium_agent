'use client'

import { Suspense, useState } from 'react'
import { useRouter, useSearchParams } from 'next/navigation'
import Link from 'next/link'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import SrLogo from '@/components/login/SrLogo'
import { api, ApiError } from '@/lib/api'
import useAuthStore from '@/store/auth'

const OAUTH_ERRORS = {
  oauth_not_configured: 'Google 로그인이 설정되지 않았습니다',
  oauth_state_mismatch: 'OAuth 인증에 실패했습니다. 다시 시도해 주세요',
  oauth_token_exchange_failed: 'Google 인증 토큰 교환에 실패했습니다',
  oauth_userinfo_failed: 'Google 사용자 정보를 가져오지 못했습니다',
  oauth_network_error: 'Google 서버와 통신 중 오류가 발생했습니다',
  oauth_db_error: '계정 처리 중 오류가 발생했습니다',
  account_inactive: '비활성화된 계정입니다',
}

function GoogleIcon() {
  return (
    <svg viewBox="0 0 24 24" className="size-4" aria-hidden="true">
      <path
        d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z"
        fill="#4285F4"
      />
      <path
        d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"
        fill="#34A853"
      />
      <path
        d="M5.84 14.1c-.22-.66-.35-1.36-.35-2.1s.13-1.44.35-2.1V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l3.66-2.83z"
        fill="#FBBC05"
      />
      <path
        d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.83c.87-2.6 3.3-4.52 6.16-4.52z"
        fill="#EA4335"
      />
    </svg>
  )
}

function LoginContent() {
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)
  const setUser = useAuthStore((s) => s.setUser)
  const router = useRouter()
  const searchParams = useSearchParams()

  const oauthError = searchParams.get('error')
  const oauthErrorMessage = oauthError ? OAUTH_ERRORS[oauthError] || '로그인에 실패했습니다' : ''

  async function handleLogin(e) {
    e.preventDefault()
    setError('')
    setLoading(true)
    try {
      await api.auth.login(email, password)
      const user = await api.auth.me()
      setUser(user)
      router.push('/')
    } catch (err) {
      setError(err instanceof ApiError ? err.message : '로그인에 실패했습니다')
    } finally {
      setLoading(false)
    }
  }

  function handleGoogleLogin() {
    window.location.href = api.auth.googleUrl()
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-background px-4">
      <div className="w-full max-w-sm">
        {/* 로고 */}
        <div className="mb-8 flex flex-col items-center gap-3">
          <SrLogo className="size-24" />
          <div className="text-center">
            <h1 className="text-xl font-bold tracking-tight">Where Winds Meet</h1>
            <p className="mt-1 text-xs text-muted-foreground">계정에 로그인하세요</p>
          </div>
        </div>

        {/* 로그인 폼 */}
        <form onSubmit={handleLogin} className="flex flex-col gap-3">
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
              autoComplete="current-password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
            />
          </div>

          {(error || oauthErrorMessage) && (
            <p className="text-xs text-destructive">{error || oauthErrorMessage}</p>
          )}

          <Button type="submit" size="lg" className="mt-1 w-full" disabled={loading}>
            {loading ? '로그인 중...' : '로그인'}
          </Button>
        </form>

        {/* 구분선 */}
        <div className="my-4 flex items-center gap-3">
          <div className="h-px flex-1 bg-border" />
          <span className="text-[10px] text-muted-foreground">또는</span>
          <div className="h-px flex-1 bg-border" />
        </div>

        {/* 구글 로그인 */}
        <Button
          variant="outline"
          size="lg"
          className="w-full gap-2"
          onClick={handleGoogleLogin}
        >
          <GoogleIcon />
          Google로 계속하기
        </Button>

        {/* 회원가입 링크 */}
        <p className="mt-4 text-center text-xs text-muted-foreground">
          계정이 없으신가요?{' '}
          <Link href="/register" className="font-medium text-foreground hover:underline">
            회원가입
          </Link>
        </p>
      </div>
    </div>
  )
}

export default function LoginPage() {
  return (
    <Suspense fallback={null}>
      <LoginContent />
    </Suspense>
  )
}
