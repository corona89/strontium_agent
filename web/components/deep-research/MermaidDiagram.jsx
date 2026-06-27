'use client'

import { useEffect, useId, useRef, useState } from 'react'

function isDarkMode() {
  if (typeof document === 'undefined') return false
  return document.documentElement.classList.contains('dark')
}

export default function MermaidDiagram({ chart }) {
  const reactId = useId()
  const containerRef = useRef(null)
  const [svg, setSvg] = useState(null)
  const [error, setError] = useState(null)
  const renderSeq = useRef(0)

  useEffect(() => {
    let cancelled = false
    const seq = ++renderSeq.current

    async function run() {
      try {
        const mermaid = (await import('mermaid')).default
        mermaid.initialize({
          startOnLoad: false,
          securityLevel: 'strict',
          theme: isDarkMode() ? 'dark' : 'default',
          fontFamily: 'inherit',
        })
        const id = `mermaid-${reactId.replace(/[^a-zA-Z0-9]/g, '')}-${seq}`
        const { svg: rendered } = await mermaid.render(id, chart.trim())
        if (!cancelled) {
          setSvg(rendered)
          setError(null)
        }
      } catch (e) {
        if (!cancelled) setError(e instanceof Error ? e.message : String(e))
      }
    }

    run()
    return () => {
      cancelled = true
    }
  }, [chart, reactId])

  if (error) {
    return (
      <div className="my-2 rounded-md border border-destructive/30 bg-destructive/5 p-3">
        <p className="mb-1 text-xs font-medium text-destructive">
          Mermaid 다이어그램 렌더링에 실패했습니다.
        </p>
        <pre className="overflow-auto text-[11px] text-muted-foreground">{chart}</pre>
      </div>
    )
  }

  if (!svg) {
    return (
      <div className="mermaid-chart my-2 flex justify-center rounded-md border bg-card p-3">
        <span className="text-xs text-muted-foreground">다이어그램 렌더링 중…</span>
      </div>
    )
  }

  return (
    <div
      ref={containerRef}
      className="mermaid-chart my-2 flex justify-center overflow-x-auto rounded-md border bg-card p-3"
      dangerouslySetInnerHTML={{ __html: svg }}
    />
  )
}
