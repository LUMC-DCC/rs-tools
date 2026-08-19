import { Download, Info } from 'lucide-react'
import { useState } from 'react'

import type { ToolItem } from '../../types'
import ToolFields from './ToolFields'

interface ToolCardProps {
  tool: ToolItem
  busy: boolean
  disabled: boolean
  isFiltered: boolean
  onDownload: () => void
  onFilter: () => void
  onFocusField: (path: string) => void
}

/** One downloadable artifact: what it produces, and what it reads to do so. */
export default function ToolCard({
  tool,
  busy,
  disabled,
  isFiltered,
  onDownload,
  onFilter,
  onFocusField,
}: ToolCardProps) {
  const [showDetails, setShowDetails] = useState(false)

  return (
    <article className="tool-card">
      <div className="tool-card-main">
        <button
          type="button"
          className="button button-tool tool-card-action"
          disabled={disabled}
          onClick={onDownload}
        >
          <Download size={13} aria-hidden="true" />
          <span className="tool-card-label">{busy ? 'Preparing…' : tool.action}</span>
        </button>
        <button
          type="button"
          className={`icon-button ${showDetails ? 'is-open' : ''}`}
          aria-label={`About ${tool.action}`}
          aria-expanded={showDetails}
          onClick={() => setShowDetails((open) => !open)}
        >
          <Info size={14} aria-hidden="true" />
        </button>
      </div>

      {showDetails && (
        <ToolFields
          description={tool.description}
          fields={tool.fields}
          isFiltered={isFiltered}
          onFilter={onFilter}
          onFocusField={onFocusField}
        />
      )}
    </article>
  )
}
