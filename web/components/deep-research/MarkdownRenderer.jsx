'use client'

import { useState } from 'react'
import { Check, Copy } from 'lucide-react'
import Markdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import rehypeHighlight from 'rehype-highlight'
import { cn } from '@/lib/utils'
import MermaidDiagram from './MermaidDiagram'
import DrawioDiagram from './DrawioDiagram'

function extractText(node) {
  if (node == null || node === false) return ''
  if (typeof node === 'string') return node
  if (typeof node === 'number') return String(node)
  if (Array.isArray(node)) return node.map(extractText).join('')
  if (typeof node === 'object' && node.props) return extractText(node.props.children)
  return ''
}

const components = {
  a({ href, children, ...props }) {
    return (
      <a
        href={href}
        target="_blank"
        rel="noopener noreferrer"
        className="text-primary underline underline-offset-2 hover:text-primary/80"
        {...props}
      >
        {children}
      </a>
    )
  },
  pre({ children }) {
    const codeEl = Array.isArray(children) ? children[0] : children
    const className = codeEl?.props?.className || ''
    const match = /language-(\w+)/.exec(className)
    const lang = match?.[1]
    const raw = extractText(codeEl?.props?.children)

    if (lang === 'mermaid') return <MermaidDiagram chart={raw} />
    if (lang === 'drawio') return <DrawioDiagram xml={raw} />

    return (
      <CodeBlock lang={lang} raw={raw} className={className}>
        {children}
      </CodeBlock>
    )
  },
}

function CodeBlock({ lang, raw, className, children }) {
  const [copied, setCopied] = useState(false)

  function copy() {
    if (!navigator.clipboard) return
    navigator.clipboard.writeText(raw).then(() => {
      setCopied(true)
      setTimeout(() => setCopied(false), 1500)
    })
  }

  return (
    <div className="group/code my-3 overflow-hidden rounded-md border">
      <div className="flex items-center justify-between border-b bg-muted px-3 py-1">
        <span className="text-[10px] font-medium uppercase tracking-wide text-muted-foreground">
          {lang || 'code'}
        </span>
        <button
          type="button"
          onClick={copy}
          className="flex items-center gap-1 rounded px-1.5 py-0.5 text-[10px] text-muted-foreground transition-colors hover:bg-foreground/10 hover:text-foreground"
        >
          {copied ? <Check size={11} /> : <Copy size={11} />}
          {copied ? '복사됨' : '복사'}
        </button>
      </div>
      <pre className={cn('overflow-auto bg-card p-3 text-[12px] leading-relaxed', className)}>
        {children}
      </pre>
    </div>
  )
}

export default function MarkdownRenderer({ children, className }) {
  return (
    <div className={cn('md-content text-sm leading-relaxed text-foreground', className)}>
      <Markdown
        remarkPlugins={[remarkGfm]}
        rehypePlugins={[[rehypeHighlight, { detect: true, ignoreMissing: true }]]}
        components={components}
      >
        {children}
      </Markdown>
    </div>
  )
}
