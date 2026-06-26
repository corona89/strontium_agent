'use client'

import { useState, useEffect, useCallback } from 'react'
import { Button } from '@/components/ui/button'
import { api, ApiError } from '@/lib/api'

const ACTION_LABELS = {
  signup: '회원가입',
  oauth_signup: 'OAuth 가입',
  update_profile: '프로필 변경',
  change_password: '비밀번호 변경',
  'admin.change_role': '역할 변경 (운영자)',
  'admin.reset_password': '비밀번호 초기화 (운영자)',
  'admin.deactivate_user': '사용자 비활성화 (운영자)',
}

export default function AuditLogsPage() {
  const [logs, setLogs] = useState([])
  const [total, setTotal] = useState(0)
  const [page, setPage] = useState(1)
  const [loading, setLoading] = useState(true)
  const [msg, setMsg] = useState('')

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const data = await api.admin.auditLogs(page)
      setLogs(data.logs)
      setTotal(data.total)
    } catch (err) {
      setMsg(err instanceof ApiError ? err.message : '로드에 실패했습니다')
    } finally {
      setLoading(false)
    }
  }, [page])

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    load()
  }, [load])

  const pageSize = 20
  const totalPages = Math.ceil(total / pageSize)

  function formatDetail(detail) {
    if (!detail) return '-'
    try {
      const obj = JSON.parse(detail)
      return Object.entries(obj)
        .map(([k, v]) => `${k}: ${JSON.stringify(v)}`)
        .join(', ')
    } catch {
      return detail
    }
  }

  return (
    <div>
      <h1 className="text-2xl font-semibold">감사 로그</h1>
      <p className="mt-1 text-sm text-muted-foreground">총 {total}건</p>

      {msg && <p className="mt-3 text-xs text-destructive">{msg}</p>}

      {loading ? (
        <p className="mt-8 text-sm text-muted-foreground">로딩 중...</p>
      ) : (
        <div className="mt-6 overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b text-left text-xs text-muted-foreground">
                <th className="pb-2 pr-4 font-medium">시간</th>
                <th className="pb-2 pr-4 font-medium">수행자</th>
                <th className="pb-2 pr-4 font-medium">대상</th>
                <th className="pb-2 pr-4 font-medium">액션</th>
                <th className="pb-2 pr-4 font-medium">상세</th>
              </tr>
            </thead>
            <tbody>
              {logs.map((log) => (
                <tr key={log.id} className="border-b">
                  <td className="py-3 pr-4 text-xs whitespace-nowrap">
                    {new Date(log.created_at).toLocaleString('ko-KR')}
                  </td>
                  <td className="py-3 pr-4 text-xs">
                    {log.actor_email || '-'}
                  </td>
                  <td className="py-3 pr-4 text-xs">
                    {log.target_email || '-'}
                  </td>
                  <td className="py-3 pr-4 text-xs">
                    {ACTION_LABELS[log.action] || log.action}
                  </td>
                  <td className="py-3 pr-4 text-xs text-muted-foreground">
                    {formatDetail(log.detail)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {totalPages > 1 && (
        <div className="mt-4 flex items-center gap-2">
          <Button
            size="xs"
            variant="outline"
            onClick={() => setPage((p) => Math.max(1, p - 1))}
            disabled={page === 1}
          >
            이전
          </Button>
          <span className="text-xs text-muted-foreground">
            {page} / {totalPages}
          </span>
          <Button
            size="xs"
            variant="outline"
            onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
            disabled={page === totalPages}
          >
            다음
          </Button>
        </div>
      )}
    </div>
  )
}
