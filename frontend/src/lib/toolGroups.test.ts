import { describe, expect, it } from 'vitest'

import { buildToolGroups, groupTemplates, RSM_JSON_TOOL } from './toolGroups'
import type { GeneratorCategory, GeneratorInfo, ToolGroup } from '../types'

function find(groups: ToolGroup[], id: GeneratorCategory): ToolGroup {
  const group = groups.find((candidate) => candidate.id === id)
  if (!group) throw new Error(`No ${id} group was built`)
  return group
}

function generator(overrides: Partial<GeneratorInfo>): GeneratorInfo {
  return {
    id: 'citation-cff',
    label: 'CITATION.cff',
    description: 'Citation metadata.',
    filename: 'CITATION.cff',
    category: 'metadata',
    fields: [],
    templates: [],
    ...overrides,
  }
}

describe('buildToolGroups', () => {
  it('groups generators by the category the API assigns', () => {
    const groups = buildToolGroups([
      generator({ id: 'codemeta', label: 'codemeta.json', category: 'metadata' }),
      generator({ id: 'readme', label: 'README.md', category: 'documentation' }),
      generator({ id: 'license', label: 'LICENSE', category: 'project' }),
      generator({ id: 'repository', label: 'repository scaffold', category: 'repository' }),
    ])

    expect(groups.map((group) => group.id)).toEqual([
      'repository',
      'metadata',
      'documentation',
      'project',
    ])
    expect(groups[2].tools.map((tool) => tool.id)).toEqual(['readme'])
    expect(groups[3].tools.map((tool) => tool.id)).toEqual(['license'])
  })

  it('states the whole action on every button', () => {
    const groups = buildToolGroups([generator({ id: 'codemeta', label: 'codemeta.json' })])

    expect(find(groups, 'metadata').tools.map((tool) => tool.action)).toEqual([
      'Download RSM JSON',
      'Download codemeta.json',
    ])
  })

  it('leads the metadata group with the stored document', () => {
    const groups = buildToolGroups([generator({})])

    expect(find(groups, 'metadata').tools[0]).toBe(RSM_JSON_TOOL)
  })

  it('omits a group that has no tools', () => {
    // The stored document is always downloadable, so the metadata group is the
    // one group that survives an empty catalogue.
    const groups = buildToolGroups([])

    expect(groups.map((group) => group.id)).toEqual(['metadata'])
  })
})

describe('groupTemplates', () => {
  it('offers a shared choice once for the whole group', () => {
    const templates = [
      { id: 'generic', label: 'Generic' },
      { id: 'python', label: 'Python' },
      { id: 'r', label: 'R' },
    ]
    const groups = buildToolGroups([
      generator({ id: 'repository', category: 'repository', templates }),
    ])

    expect(groupTemplates(find(groups, 'repository'))).toEqual(templates)
  })

  it('offers nothing for groups whose tools take no options', () => {
    const groups = buildToolGroups([generator({})])

    expect(groupTemplates(find(groups, 'metadata'))).toEqual([])
  })
})
