'use client'

import { useRouter } from 'next/navigation'
import { Menu, User, LogOut } from 'lucide-react'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
import useStore from '@/store'
import useAuthStore from '@/store/auth'
import { api } from '@/lib/api'

export default function TopNav() {
  const toggleSidebar = useStore((s) => s.toggleSidebar)
  const user = useAuthStore((s) => s.user)
  const clearUser = useAuthStore((s) => s.clearUser)
  const router = useRouter()

  async function handleLogout() {
    await api.auth.logout().catch(() => {})
    clearUser()
    router.push('/login')
  }

  const displayName = user?.nickname || user?.email || '...'

  return (
    <header className="flex h-[60px] shrink-0 items-center justify-between border-b bg-card px-4">
      {/* 좌측: 사이드바 토글 + 앱 이름 */}
      <div className="flex items-center gap-3">
        <button
          onClick={toggleSidebar}
          className="rounded-md p-2 hover:bg-accent transition-colors"
          aria-label="사이드바 토글"
        >
          <Menu size={20} />
        </button>
        <span className="font-semibold text-sm">Strontium Agent</span>
      </div>

      {/* 우측: 사용자명 + 드롭다운 */}
      <DropdownMenu>
        <DropdownMenuTrigger className="flex items-center gap-2 rounded-md px-3 py-2 text-sm hover:bg-accent transition-colors">
          <span>{displayName}</span>
          <Menu size={16} />
        </DropdownMenuTrigger>
        <DropdownMenuContent align="end" className="w-40">
          <DropdownMenuItem onClick={() => router.push('/settings')}>
            <User size={14} className="mr-2" />
            프로필
          </DropdownMenuItem>
          <DropdownMenuSeparator />
          <DropdownMenuItem
            className="text-destructive focus:text-destructive"
            onClick={handleLogout}
          >
            <LogOut size={14} className="mr-2" />
            로그아웃
          </DropdownMenuItem>
        </DropdownMenuContent>
      </DropdownMenu>
    </header>
  )
}
