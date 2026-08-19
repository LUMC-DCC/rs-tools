import { useEffect, type RefObject } from 'react'

/**
 * Keep the sticky panels sized to the space actually left below the header.
 *
 * The tools panel and the drag handle are `position: sticky` and must be as
 * tall as the visible area beneath them. That distance changes as the page
 * scrolls and as the window resizes, and CSS alone cannot express it, so it is
 * published as a custom property for the stylesheets to use.
 */
export function useStickyViewport(gridRef: RefObject<HTMLDivElement | null>, ready: boolean): void {
  useEffect(() => {
    if (!ready) return
    let frame = 0
    const update = () => {
      window.cancelAnimationFrame(frame)
      frame = window.requestAnimationFrame(() => {
        const grid = gridRef.current
        if (!grid) return
        const headerBottom = document.querySelector('.site-header')?.getBoundingClientRect().bottom ?? 0
        const top = Math.max(headerBottom, grid.getBoundingClientRect().top)
        grid.style.setProperty('--workspace-viewport-top', `${top}px`)
      })
    }
    update()
    window.addEventListener('scroll', update, { passive: true })
    window.addEventListener('resize', update)
    return () => {
      window.cancelAnimationFrame(frame)
      window.removeEventListener('scroll', update)
      window.removeEventListener('resize', update)
    }
  }, [gridRef, ready])
}
