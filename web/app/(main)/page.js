'use client'

import useAuthStore from '@/store/auth'

export default function Home() {
  const user = useAuthStore((s) => s.user)
  const displayName = user?.nickname || user?.email || '사용자'

  return (
    <div className="flex flex-col">
      <h1 className="text-2xl font-semibold">
        안녕하세요, {displayName}님
      </h1>
      <p className="mt-2 text-sm text-muted-foreground">
        Where Winds Meet에 오신 것을 환영합니다. 왼쪽 메뉴에서 원하는 페이지로 이동하세요.
      </p>

      <div className="mt-8 grid gap-4 sm:grid-cols-2">
        <div className="rounded-lg border bg-card p-5">
          <h2 className="text-sm font-medium text-muted-foreground">내 계정</h2>
          <p className="mt-2 text-sm">{user?.email}</p>
          <p className="mt-1 text-xs text-muted-foreground">
            가입일: {user?.created_at ? new Date(user.created_at).toLocaleDateString('ko-KR') : '-'}
          </p>
        </div>

        <div className="rounded-lg border bg-card p-5">
          <h2 className="text-sm font-medium text-muted-foreground">빠른 작업</h2>
          <p className="mt-2 text-sm text-muted-foreground">
            설정 페이지에서 닉네임과 비밀번호를 변경할 수 있습니다.
          </p>
        </div>
      </div>
    </div>
  )
}
