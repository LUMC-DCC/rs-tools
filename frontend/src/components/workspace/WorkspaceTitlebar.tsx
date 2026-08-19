import { ArrowLeft } from 'lucide-react'
import { Link } from 'react-router-dom'

import type { SaveState } from '../../hooks/useAutosave'

const SAVE_LABELS: Record<SaveState, string> = {
  idle: 'Up to date',
  dirty: 'Waiting to save…',
  saving: 'Saving…',
  saved: 'Saved',
  invalid: 'Invalid JSON',
  error: 'Not saved',
}

interface WorkspaceTitlebarProps {
  title: string
  saveState: SaveState
}

export default function WorkspaceTitlebar({ title, saveState }: WorkspaceTitlebarProps) {
  return (
    <div className="workspace-titlebar">
      <div className="workspace-heading">
        <Link className="icon-button back-link" to="/" aria-label="Back home" title="Back home">
          <ArrowLeft size={16} aria-hidden="true" />
        </Link>
        <h1>{title}</h1>
      </div>
      <div className={`save-indicator save-${saveState}`} aria-live="polite">
        <span />
        {SAVE_LABELS[saveState]}
      </div>
    </div>
  )
}
