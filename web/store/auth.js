import { create } from 'zustand'

const useAuthStore = create((set) => ({
  user: null,       // { id, email, nickname, is_active, ... }
  setUser: (user) => set({ user }),
  clearUser: () => set({ user: null }),
}))

export default useAuthStore
