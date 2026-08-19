import { CircleArrowUp } from 'lucide-react'
import { type RefObject, useEffect, useRef, useState } from 'react'

interface MetadataBackToTopProps {
  panelRef: RefObject<HTMLElement | null>
}

interface ButtonPosition {
  left: number
  visible: boolean
}

/** A floating shortcut that stays visually attached to the metadata column. */
export default function MetadataBackToTop({ panelRef }: MetadataBackToTopProps) {
  const buttonRef = useRef<HTMLButtonElement | null>(null)
  const [position, setPosition] = useState<ButtonPosition>({ left: 0, visible: false })

  useEffect(() => {
    const panel = panelRef.current
    if (!panel) return

    let animationFrame = 0

    const update = () => {
      window.cancelAnimationFrame(animationFrame)
      animationFrame = window.requestAnimationFrame(() => {
        const rect = panel.getBoundingClientRect()
        const panelTop = rect.top + window.scrollY
        const buttonWidth = buttonRef.current?.getBoundingClientRect().width ?? 0
        const sharedGap = Number.parseFloat(
          getComputedStyle(panel).getPropertyValue('--workspace-column-gap'),
        )
        const inset = Number.isFinite(sharedGap) ? sharedGap : 0
        const left = Math.round(
          Math.max(
            inset,
            Math.min(window.innerWidth - buttonWidth - inset, rect.right - buttonWidth - inset),
          ),
        )
        const visible = window.scrollY > panelTop + 240 && rect.bottom > 80

        setPosition((current) =>
          current.left === left && current.visible === visible ? current : { left, visible },
        )
      })
    }

    const resizeObserver = new ResizeObserver(update)
    resizeObserver.observe(panel)
    window.addEventListener('scroll', update, { passive: true })
    window.addEventListener('resize', update)
    update()

    return () => {
      window.cancelAnimationFrame(animationFrame)
      resizeObserver.disconnect()
      window.removeEventListener('scroll', update)
      window.removeEventListener('resize', update)
    }
  }, [panelRef])

  const scrollToTop = () => {
    const panel = panelRef.current
    if (!panel) return

    const headerHeight =
      document.querySelector<HTMLElement>('.site-header')?.getBoundingClientRect().height ?? 0
    const panelTop = panel.getBoundingClientRect().top + window.scrollY
    window.scrollTo({ top: Math.max(0, panelTop - headerHeight), behavior: 'smooth' })
  }

  return (
    <button
      ref={buttonRef}
      type="button"
      className={`metadata-back-to-top ${position.visible ? 'is-visible' : ''}`}
      style={{ left: position.left }}
      aria-label="Back to top of metadata"
      title="Back to top of metadata"
      tabIndex={position.visible ? 0 : -1}
      onClick={scrollToTop}
    >
      <CircleArrowUp size={20} aria-hidden="true" />
    </button>
  )
}
