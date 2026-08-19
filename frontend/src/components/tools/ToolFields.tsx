import type { GeneratorField } from '../../types'

interface ToolFieldsProps {
  description: string
  fields: GeneratorField[]
  isFiltered: boolean
  onFilter: () => void
  onFocusField: (path: string) => void
}

/** What one tool reads from the metadata, with a link to each field. */
export default function ToolFields({
  description,
  fields,
  isFiltered,
  onFilter,
  onFocusField,
}: ToolFieldsProps) {
  const groups = groupFields(fields)
  return (
    <div className="tool-details">
      <p>{description}</p>
      {groups.length > 0 ? (
        <>
          <div className="tool-details-heading">
            <p>Metadata used</p>
            <button type="button" className="link-button" onClick={onFilter}>
              {isFiltered ? 'Show all fields' : 'Show only these'}
            </button>
          </div>
          <ul className="tool-field-list">
            {groups.map((group) => (
              <li key={group.path}>
                <button
                  type="button"
                  className="field-link"
                  onClick={() => onFocusField(group.path)}
                >
                  {group.label}
                </button>
                {group.details.length > 0 && (
                  <span className="field-details">({group.details.join(', ')})</span>
                )}
              </li>
            ))}
          </ul>
        </>
      ) : (
        <p className="github-note">This tool uses the whole document.</p>
      )}
    </div>
  )
}

interface FieldGroup {
  path: string
  label: string
  details: string[]
}

/**
 * Collapse a flat list of JSON Pointers into one entry per top-level field.
 *
 * The API reports every path a generator reads, including deeply nested ones.
 * Listing them raw would be a wall of pointers, so nested paths become a short
 * parenthetical under the top-level field they belong to.
 */
function groupFields(fields: GeneratorField[]): FieldGroup[] {
  const groups = new Map<string, { path: string; label: string; nested: GeneratorField[] }>()

  for (const field of fields) {
    const parts = field.path.split('/').filter(Boolean)
    if (parts.length === 0) continue
    const path = `/${parts[0]}`
    const current = groups.get(path) || { path, label: humanize(parts[0]), nested: [] }
    if (parts.length === 1) current.label = field.label
    else current.nested.push(field)
    groups.set(path, current)
  }

  return [...groups.values()].map((group) => {
    // Only the leaves say anything new: an intermediate path is already implied
    // by the leaf below it.
    const leaves = group.nested.filter(
      (field) => !group.nested.some((other) => other.path.startsWith(`${field.path}/`)),
    )
    return {
      path: group.path,
      label: group.label,
      details: [...new Set(leaves.map((field) => nestedFieldLabel(field.path)).filter(Boolean))],
    }
  })
}

function nestedFieldLabel(path: string): string {
  return path
    .split('/')
    .filter(Boolean)
    .slice(1)
    .filter((part) => part !== 'entries' && part !== '0')
    .map(humanize)
    .join(' › ')
}

function humanize(value: string): string {
  return value.replaceAll('_', ' ')
}
