import Sidebar from '@/components/layout/Sidebar'
import TopNav from '@/components/layout/TopNav'
import AuthInitializer from '@/components/auth/AuthInitializer'

export default function MainLayout({ children }) {
  return (
    <div className="flex h-screen flex-col">
      <AuthInitializer />
      <TopNav />
      <div className="flex flex-1 overflow-hidden">
        <Sidebar />
        <main className="flex-1 overflow-auto p-6">
          {children}
        </main>
      </div>
    </div>
  )
}
