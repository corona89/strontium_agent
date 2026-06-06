'use client'

import Link from 'next/link'
import { usePathname } from 'next/navigation'
import { Home, Settings } from 'lucide-react'
import { cn } from '@/lib/utils'
import useStore from '@/store'

const navItems = [
  { href: '/', icon: Home, label: '홈' },
  { href: '/settings', icon: Settings, label: '설정' },
]

export default function Sidebar() {
  const sidebarOpen = useStore((s) => s.sidebarOpen)
  const pathname = usePathname()

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
