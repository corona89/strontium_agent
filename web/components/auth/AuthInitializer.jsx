'use client'

import { useEffect } from 'react'
import { api } from '@/lib/api'
import useAuthStore from '@/store/auth'

export default function AuthInitializer() {
  const setUser = useAuthStore((s) => s.setUser)

  useEffect(() => {
    api.auth.me().then(setUser).catch(() => {})
  }, [setUser])

  return null
}
