import { create } from 'zustand'

const useStore = create((set) => ({
  // 사이드바
  sidebarOpen: true,
  toggleSidebar: () => set((s) => ({ sidebarOpen: !s.sidebarOpen })),
}))

export default useStore
