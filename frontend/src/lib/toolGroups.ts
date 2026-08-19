import type { GeneratorInfo, ToolGroup, ToolItem } from '../types'

/**
 * Tools grouped by what they produce.
 *
 * Someone opening the panel is deciding between a whole project, machine-readable
 * metadata, software documentation, and repository community files. The backend
 * assigns each generator a category; the wording and order below stay here as
 * presentation.
 */
const GROUP_PRESENTATION = [
  {
    id: 'repository',
    title: 'Entire repositories',
    description: 'A complete project scaffold, downloaded or created straight on GitHub.',
  },
  {
    id: 'metadata',
    title: 'Metadata files',
    description: 'Machine-readable descriptions of the software, for registries and citation.',
  },
  {
    id: 'documentation',
    title: 'Documentation files',
    description: 'README and standalone Markdown pages for users, developers, and operators.',
  },
  {
    id: 'project',
    title: 'Community files',
    description: 'Policies, templates, and maintenance files carried alongside the code.',
  },
] as const

/** The workspace document itself, which is saved rather than generated. */
export const RSM_JSON_TOOL: ToolItem = {
  id: 'rsm-json',
  action: 'Download RSM JSON',
  filename: 'rsm.json',
  description: 'The metadata document you are editing, exactly as it is stored.',
  fields: [],
  templates: [],
}

/**
 * Build the grouped tool list shown in the panel.
 *
 * Every button says what it does and to what, so it reads the same out of
 * context as it does under its heading.
 */
export function buildToolGroups(generators: GeneratorInfo[]): ToolGroup[] {
  return GROUP_PRESENTATION.map((group) => {
    const tools = generators
      .filter((generator) => generator.category === group.id)
      .map(
        (generator): ToolItem => ({
          id: generator.id,
          action: `Download ${generator.label}`,
          filename: generator.filename,
          description: generator.description,
          fields: generator.fields,
          templates: generator.templates,
        }),
      )
    return {
      ...group,
      // The stored document belongs with the metadata files it sits beside,
      // and is the one people reach for most, so it leads that group.
      tools: group.id === 'metadata' ? [RSM_JSON_TOOL, ...tools] : tools,
    }
  }).filter((group) => group.tools.length > 0)
}

/**
 * Templates offered by a whole group.
 *
 * Downloading a scaffold and publishing it to GitHub render the same project,
 * so the scaffold is chosen once for the group. Offering it twice invites
 * picking Generic in one place and a language-specific scaffold in the other.
 */
export function groupTemplates(group: ToolGroup): ToolItem['templates'] {
  return group.tools.find((tool) => tool.templates.length > 0)?.templates ?? []
}
