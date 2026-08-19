import { Search, X } from 'lucide-react'
import { useRef } from 'react'

import SchemaForm from '../schema-form/SchemaForm'
import type { GeneratorInfo, SmpData, SmpSchema } from '../../types'
import MetadataBackToTop from './MetadataBackToTop'

export type EditorMode = 'form' | 'json'

interface WorkspaceEditorProps {
  data: SmpData
  fieldFilter: string
  generators: GeneratorInfo[]
  mode: EditorMode
  rawText: string
  schema: SmpSchema
  search: string
  visibleFieldCount: number
  /** True when a filter or a search is hiding some of the document. */
  narrowed: boolean
  onFieldFilterChange: (filter: string) => void
  onSearchChange: (search: string) => void
  onFormChange: (data: SmpData) => void
  onModeChange: (mode: EditorMode) => void
  onRawTextChange: (text: string) => void
}

/** The metadata panel: a generated form, or the raw document behind it. */
export default function WorkspaceEditor({
  data,
  fieldFilter,
  generators,
  mode,
  rawText,
  schema,
  search,
  visibleFieldCount,
  narrowed,
  onFieldFilterChange,
  onSearchChange,
  onFormChange,
  onModeChange,
  onRawTextChange,
}: WorkspaceEditorProps) {
  const panelRef = useRef<HTMLElement | null>(null)

  return (
    <section
      ref={panelRef}
      className={`panel editor-panel ${mode === 'json' ? 'editor-panel-raw' : ''}`}
      aria-labelledby="metadata-heading"
    >
      <div className="editor-toolbar">
        <div className="editor-heading">
          <h2 id="metadata-heading">Metadata</h2>
          {narrowed && (
            <span className="filter-summary">
              Showing {visibleFieldCount} {visibleFieldCount === 1 ? 'field' : 'fields'}
            </span>
          )}
        </div>
        <div className="editor-controls">
          {mode === 'form' && (
            <div className="field-search">
              <Search size={13} aria-hidden="true" />
              <input
                type="search"
                value={search}
                aria-label="Search metadata fields"
                placeholder="Search fields"
                onChange={(event) => onSearchChange(event.target.value)}
              />
              {search && (
                <button
                  type="button"
                  className="field-search-clear"
                  aria-label="Clear the field search"
                  onClick={() => onSearchChange('')}
                >
                  <X size={12} aria-hidden="true" />
                </button>
              )}
            </div>
          )}
          {mode === 'form' && (
            <label className="inline-field">
              <span>Fields</span>
              <select
                value={fieldFilter}
                onChange={(event) => onFieldFilterChange(event.target.value)}
              >
                <option value="all">All metadata</option>
                {generators
                  .filter((generator) => generator.fields.length > 0)
                  .map((generator) => (
                    <option value={generator.id} key={generator.id}>
                      {generator.label}
                    </option>
                  ))}
              </select>
            </label>
          )}
          <div className="toggle-group" role="group" aria-label="Editor view">
            <button
              type="button"
              className={mode === 'form' ? 'is-active' : ''}
              aria-pressed={mode === 'form'}
              onClick={() => onModeChange('form')}
            >
              Form
            </button>
            <button
              type="button"
              className={mode === 'json' ? 'is-active' : ''}
              aria-pressed={mode === 'json'}
              onClick={() => onModeChange('json')}
            >
              Raw JSON
            </button>
          </div>
        </div>
      </div>

      {mode === 'form' ? (
        visibleFieldCount === 0 ? (
          <p className="empty-state">
            No field matches “{search}”. Field names come from the schema, so try part of one,
            such as <code>license</code>.
          </p>
        ) : (
          <SchemaForm
            data={data}
            formKey={`${fieldFilter}:${search}`}
            schema={schema}
            onChange={onFormChange}
          />
        )
      ) : (
        <div className="raw-editor-wrap">
          <textarea
            id="raw-smp-json"
            aria-label="Complete RSM document"
            className="json-editor raw-json-editor"
            value={rawText}
            onChange={(event) => onRawTextChange(event.target.value)}
            spellCheck={false}
          />
        </div>
      )}

      <MetadataBackToTop panelRef={panelRef} />
    </section>
  )
}
