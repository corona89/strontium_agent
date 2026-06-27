'use client'

import Link from 'next/link'
import { usePathname } from 'next/navigation'
import { Home, Settings, Users, Shield, FileText, Cpu, Microscope } from 'lucide-react'
import { cn } from '@/lib/utils'
import useStore from '@/store'
import useAuthStore from '@/store/auth'

const ALL_NAV_ITEMS = [
  { href: '/', icon: Home, label: '홈', function: null },
  { href: '/settings', icon: Settings, label: '설정', function: 'settings', action: 'read' },
  { href: '/users', icon: Users, label: '사용자', function: 'users', action: 'read' },
  { href: '/roles', icon: Shield, label: '역할 관리', function: 'roles', action: 'read' },
  { href: '/audit-logs', icon: FileText, label: '감사 로그', function: 'audit', action: 'read' },
  { href: '/deep-research', icon: Microscope, label: '딥 리서치', function: 'deep_research', action: 'read' },
  { href: '/models', icon: Cpu, label: '모델 관리', function: 'models', action: 'read' },
]

export default function Sidebar() {
  const sidebarOpen = useStore((s) => s.sidebarOpen)
  const pathname = usePathname()
  const user = useAuthStore((s) => s.user)
  const permissions = user?.permissions || {}

  const navItems = ALL_NAV_ITEMS.filter((item) => {
    if (!item.function) return true
    return permissions[item.function]?.[item.action]
  })

  return (
    <aside
      className={cn(
        'flex flex-col border-r bg-card transition-all duration-300 shrink-0',
        sidebarOpen ? 'w-60' : 'w-16'
      )}
    >
      <nav className="flex flex-col gap-1 p-2 pt-4">
        {navItems.map(({ href, icon: Icon, label }) => {
          const active = pathname === href
          return (
            <Link
              key={href}
              href={href}
              className={cn(
                'flex items-center gap-3 rounded-md px-3 py-2 text-sm transition-colors',
                'hover:bg-accent hover:text-accent-foreground',
                active && 'bg-accent text-accent-foreground font-medium'
              )}
            >
              <Icon size={18} className="shrink-0" />
              {sidebarOpen && <span className="truncate">{label}</span>}
            </Link>
          )
        })}
      </nav>
    </aside>
  )
}
