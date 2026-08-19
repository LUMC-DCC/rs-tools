import { type RefObject, useEffect, useRef } from 'react'

const DEFAULT_TOOLS_PERCENT = 40
const MIN_TOOLS_PERCENT = 20
const MAX_TOOLS_PERCENT = 80
const STORAGE_KEY = 'rs-tools:tools-panel-percent'

function clamp(percent: number): number {
  return Math.min(Math.max(percent, MIN_TOOLS_PERCENT), MAX_TOOLS_PERCENT)
}

export function initialToolsPercent(): number {
  if (typeof window === 'undefined') return DEFAULT_TOOLS_PERCENT
  const stored = Number(window.localStorage.getItem(STORAGE_KEY))
  return Number.isFinite(stored) && stored > 0 ? clamp(stored) : DEFAULT_TOOLS_PERCENT
}

interface WorkspaceResizerProps {
  gridRef: RefObject<HTMLDivElement | null>
  toolsPercent: number
  onChange: (percent: number) => void
  onResizeStateChange: (resizing: boolean) => void
}

export default function WorkspaceResizer({
  gridRef,
  toolsPercent,
  onChange,
  onResizeStateChange,
}: WorkspaceResizerProps) {
  const percentRef = useRef(toolsPercent)
  const start = useRef<{ clientX: number; percent: number } | null>(null)

  useEffect(() => {
    percentRef.current = toolsPercent
  }, [toolsPercent])

  const update = (percent: number) => {
    const next = clamp(percent)
    percentRef.current = next
    onChange(next)
  }

  const finish = () => {
    start.current = null
    onResizeStateChange(false)
    window.localStorage.setItem(STORAGE_KEY, String(percentRef.current))
  }

  const adjust = (change: number) => {
    update(percentRef.current + change)
    window.localStorage.setItem(STORAGE_KEY, String(percentRef.current))
  }

  return (
    <div
      className="workspace-resizer"
      role="separator"
      aria-label="Resize metadata and tools panels"
      aria-orientation="vertical"
      aria-valuemin={MIN_TOOLS_PERCENT}
      aria-valuemax={MAX_TOOLS_PERCENT}
      aria-valuenow={Math.round(toolsPercent)}
      aria-valuetext={`${Math.round(toolsPercent)}% tools, ${Math.round(100 - toolsPercent)}% metadata`}
      tabIndex={0}
      title="Drag to resize. Double-click to reset."
      onDoubleClick={() => adjust(DEFAULT_TOOLS_PERCENT - percentRef.current)}
      onKeyDown={(event) => {
        const step = event.shiftKey ? 5 : 2
        if (event.key === 'ArrowLeft') adjust(step)
        else if (event.key === 'ArrowRight') adjust(-step)
        else if (event.key === 'Home') adjust(MIN_TOOLS_PERCENT - percentRef.current)
        else if (event.key === 'End') adjust(MAX_TOOLS_PERCENT - percentRef.current)
        else return
        event.preventDefault()
      }}
      onPointerDown={(event) => {
        start.current = { clientX: event.clientX, percent: percentRef.current }
        onResizeStateChange(true)
        event.currentTarget.setPointerCapture(event.pointerId)
      }}
      onPointerMove={(event) => {
        const resizeStart = start.current
        const bounds = gridRef.current?.getBoundingClientRect()
        if (!resizeStart || !bounds) return
        update(resizeStart.percent + ((resizeStart.clientX - event.clientX) / bounds.width) * 100)
      }}
      onPointerUp={(event) => {
        if (!start.current) return
        event.currentTarget.releasePointerCapture(event.pointerId)
        finish()
      }}
      onPointerCancel={finish}
    />
  )
}
