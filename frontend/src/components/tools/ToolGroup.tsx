import { ChevronDown } from 'lucide-react'
import type { ReactNode } from 'react'

import type { GeneratorTemplate, ToolGroup as ToolGroupModel } from '../../types'

interface ToolGroupProps {
  group: ToolGroupModel
  count: number
  open: boolean
  forceOpen: boolean
  templates: GeneratorTemplate[]
  selectedTemplate?: string
  onOpenChange: (open: boolean) => void
  onSelectTemplate: (templateId: string) => void
  children: ReactNode
}

/** A titled set of related tools, with any choice they share stated once. */
export default function ToolGroup({
  group,
  count,
  open,
  forceOpen,
  templates,
  selectedTemplate,
  onOpenChange,
  onSelectTemplate,
  children,
}: ToolGroupProps) {
  const headingId = `tool-group-${group.id}`

  return (
    <details
      className="tool-group"
      open={forceOpen || open}
      onToggle={(event) => {
        if (forceOpen) {
          if (!event.currentTarget.open) event.currentTarget.open = true
          return
        }
        onOpenChange(event.currentTarget.open)
      }}
    >
      <summary className="tool-group-header" aria-labelledby={headingId}>
        <span className="tool-group-heading" id={headingId} role="heading" aria-level={3}>
          {group.title}
        </span>
        <span className="tool-group-count" aria-label={`${count} ${count === 1 ? 'tool' : 'tools'}`}>
          {count}
        </span>
        <ChevronDown size={16} aria-hidden="true" />
      </summary>

      <div className="tool-group-content">
        <p className="tool-group-description">{group.description}</p>

        {templates.length > 0 && (
          <label className="inline-field tool-group-options">
            <span>Language</span>
            <select
              value={selectedTemplate}
              onChange={(event) => onSelectTemplate(event.target.value)}
            >
              {templates.map((template) => (
                <option value={template.id} key={template.id}>
                  {template.label}
                </option>
              ))}
            </select>
          </label>
        )}

        <ul className="tool-list">{children}</ul>
      </div>
    </details>
  )
}
