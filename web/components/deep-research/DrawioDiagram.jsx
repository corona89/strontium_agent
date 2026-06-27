'use client'

import { useEffect, useRef, useState } from 'react'

const VIEWER_URL =
  'https://viewer.diagrams.net/?embed=1&proto=json&ui=min&layers=1&zoom=1&chrome=0&highlight=0000ff'

export default function DrawioDiagram({ xml }) {
  const iframeRef = useRef(null)
  const [status, setStatus] = useState('loading')
  const [height, setHeight] = useState(400)
  const source = xml.trim()

  useEffect(() => {
    function onMessage(event) {
      const win = iframeRef.current?.contentWindow
      if (!win || event.source !== win) return
      let msg
      try {
        msg = typeof event.data === 'string' ? JSON.parse(event.data) : event.data
      } catch {
        return
      }
      if (!msg || typeof msg !== 'object') return

      if (msg.event === 'init') {
        win.postMessage(
          JSON.stringify({
            action: 'load',
            xml: source,
            autosave: 0,
            diagram: source,
          }),
          '*'
        )
        setStatus('loaded')
      } else if (msg.event === 'load') {
        setStatus('loaded')
      } else if (msg.event === 'error') {
        setStatus('error')
      }
    }

    window.addEventListener('message', onMessage)
    return () => window.removeEventListener('message', onMessage)
  }, [source])

  if (status === 'error') {
    return (
      <div className="my-2 rounded-md border border-destructive/30 bg-destructive/5 p-3">
        <p className="mb-1 text-xs font-medium text-destructive">
          draw.io 다이어그램 로드에 실패했습니다.
        </p>
        <pre className="overflow-auto text-[11px] text-muted-foreground">{source}</pre>
      </div>
    )
  }

  return (
    <div className="my-2 overflow-hidden rounded-md border bg-card">
      <iframe
        ref={iframeRef}
        src={VIEWER_URL}
        title="draw.io diagram"
        className="w-full"
        style={{ height: `${height}px`, border: '0', display: 'block' }}
        onLoad={() => {
          const win = iframeRef.current?.contentWindow
          if (win) {
            win.postMessage(
              JSON.stringify({ action: 'load', xml: source, diagram: source }),
              '*'
            )
          }
        }}
      />
      {status === 'loading' && (
        <p className="p-2 text-center text-xs text-muted-foreground">
          다이어그램 로드 중…
        </p>
      )}
      <ResizeObserver onHeight={setHeight} iframeRef={iframeRef} />
    </div>
  )
}

function ResizeObserver({ onHeight, iframeRef }) {
  useEffect(() => {
    const el = iframeRef.current
    if (!el) return
    function update() {
      try {
        const doc = el.contentDocument
        if (doc && doc.body) {
          const h = Math.max(400, doc.body.scrollHeight)
          onHeight(h)
        }
      } catch {
        /* cross-origin — keep default height */
      }
    }
    const id = setInterval(update, 800)
    return () => clearInterval(id)
  }, [onHeight, iframeRef])
  return null
}
