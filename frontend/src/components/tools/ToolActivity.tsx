import { RSM_JSON_TOOL } from '../../lib/toolGroups'
import type { ToolGroup } from '../../types'
import { GITHUB_PUBLISH_ID } from './ToolsPanel'

interface ToolActivityProps {
  activeTool: string | null
  groups: ToolGroup[]
}

/** What the panel is currently doing, announced to assistive technology. */
export default function ToolActivity({ activeTool, groups }: ToolActivityProps) {
  const label = activityLabel(activeTool, groups)
  if (!label) return null
  return (
    <div className="tool-activity" role="status" aria-live="polite">
      <span className="tool-activity-spinner" aria-hidden="true" />
      <span>{label}</span>
    </div>
  )
}

function activityLabel(activeTool: string | null, groups: ToolGroup[]): string | null {
  if (!activeTool) return null
  if (activeTool === RSM_JSON_TOOL.id) return `Preparing ${RSM_JSON_TOOL.filename}…`
  if (activeTool === GITHUB_PUBLISH_ID) return 'Creating the repository on GitHub…'
  const tool = groups.flatMap((group) => group.tools).find((entry) => entry.id === activeTool)
  return tool ? `Generating ${tool.filename}…` : 'Working…'
}
