import type { ReactNode } from 'react'

import BrandHeader from './BrandHeader'

interface CenteredStateProps {
  title: string
  eyebrow?: string
  /** Rendered above the title, for a spinner or an icon. */
  leading?: ReactNode
  children?: ReactNode
}

/**
 * A whole-page message: loading, missing, or failed.
 *
 * These states are otherwise identical apart from their wording, and every one
 * of them still needs the header, so they share one shell rather than three
 * copies of it.
 */
export default function CenteredState({
  title,
  eyebrow,
  leading,
  children,
}: CenteredStateProps) {
  return (
    <div className="app-shell">
      <BrandHeader />
      <main className="centered-state" aria-live="polite">
        {leading}
        {eyebrow && <p className="eyebrow">{eyebrow}</p>}
        <h1>{title}</h1>
        {children}
      </main>
    </div>
  )
}
