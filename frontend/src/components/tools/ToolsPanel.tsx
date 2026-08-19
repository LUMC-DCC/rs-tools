import { Search, X } from 'lucide-react'
import { useEffect, useMemo, useState } from 'react'

import { buildToolGroups, groupTemplates, RSM_JSON_TOOL } from '../../lib/toolGroups'
import type {
  GeneratorCategory,
  GeneratorInfo,
  GitHubPublishResult,
  GitHubRepositoryOptions,
} from '../../types'
import GitHubPublisher from '../github/GitHubPublisher'
import ToolActivity from './ToolActivity'
import ToolCard from './ToolCard'
import ToolGroup from './ToolGroup'

interface ToolsPanelProps {
  activeFilter: string
  /** Identifier of the tool currently running, or null when the panel is idle. */
  activeTool: string | null
  generators: GeneratorInfo[]
  initialOpenGitHub?: boolean
  preferredTemplate?: string
  repositoryName: string
  workspaceId: string
  onDownload: () => void
  onError: (message: string) => void
  onFilter: (generatorId: string) => void
  onGenerate: (toolId: string, templateId?: string) => void
  onFocusField: (path: string) => void
  onPublishGitHub: (options: GitHubRepositoryOptions) => Promise<GitHubPublishResult>
}

export const GITHUB_PUBLISH_ID = 'github-repository'
const OPEN_GROUPS_STORAGE_KEY = 'rs-tools:open-tool-groups'
const TOOL_GROUP_IDS: GeneratorCategory[] = [
  'metadata',
  'documentation',
  'project',
  'repository',
]

/** Everything that can be produced from the current metadata. */
export default function ToolsPanel({
  activeFilter,
  activeTool,
  generators,
  initialOpenGitHub,
  preferredTemplate,
  repositoryName,
  workspaceId,
  onDownload,
  onError,
  onFilter,
  onGenerate,
  onFocusField,
  onPublishGitHub,
}: ToolsPanelProps) {
  const groups = useMemo(() => buildToolGroups(generators), [generators])
  const [chosenTemplates, setChosenTemplates] = useState<Record<string, string>>({})
  const [toolSearch, setToolSearch] = useState('')
  const [openGroups, setOpenGroups] = useState<Set<GeneratorCategory>>(() =>
    initialOpenGroups(Boolean(initialOpenGitHub)),
  )

  useEffect(() => {
    try {
      window.sessionStorage.setItem(OPEN_GROUPS_STORAGE_KEY, JSON.stringify([...openGroups]))
    } catch {
      // Storage can be unavailable in privacy modes; the accordion still works
      // for the current page lifetime.
    }
  }, [openGroups])

  const busy = activeTool !== null
  const query = toolSearch.trim().toLocaleLowerCase()
  const visibleGroups = useMemo(
    () =>
      groups
        .map((group) => {
          const groupMatches = matchesToolSearch(query, group.title, group.description)
          const tools = groupMatches
            ? group.tools
            : group.tools.filter((tool) =>
                matchesToolSearch(
                  query,
                  tool.action,
                  tool.filename,
                  tool.description,
                  ...tool.fields.flatMap((field) => [field.label, field.description]),
                ),
              )
          const showGitHub =
            group.id === 'repository' &&
            (groupMatches ||
              matchesToolSearch(
                query,
                'GitHub',
                'create publish repository online sign in account organization',
              ))

          return { group: { ...group, tools }, showGitHub, templates: groupTemplates(group) }
        })
        .filter(({ group, showGitHub }) => group.tools.length > 0 || showGitHub),
    [groups, query],
  )

  return (
    <aside className="panel tools-panel" aria-labelledby="tools-heading">
      <div className="tools-header">
        <div className="tools-heading-row">
          <h2 id="tools-heading">Tools</h2>
          <div className="field-search tool-search">
            <Search size={14} aria-hidden="true" />
            <input
              type="search"
              value={toolSearch}
              aria-label="Search tools"
              placeholder="Search tools"
              onChange={(event) => setToolSearch(event.target.value)}
            />
            {toolSearch && (
              <button
                type="button"
                className="field-search-clear"
                aria-label="Clear the tool search"
                onClick={() => setToolSearch('')}
              >
                <X size={12} aria-hidden="true" />
              </button>
            )}
          </div>
        </div>
        <p className="tools-intro">
          Every tool below builds a file from the metadata on the left. Open the info button on a
          tool to see which fields it reads.
        </p>
      </div>

      <ToolActivity activeTool={activeTool} groups={groups} />

      <div className="tool-groups">
        {visibleGroups.map(({ group, showGitHub, templates }) => {
          const selectedTemplate =
            chosenTemplates[group.id] ??
            (templates.some((template) => template.id === preferredTemplate)
              ? preferredTemplate
              : templates[0]?.id)

          return (
            <ToolGroup
              key={group.id}
              group={group}
              count={group.tools.length + (showGitHub ? 1 : 0)}
              open={openGroups.has(group.id)}
              forceOpen={Boolean(query)}
              templates={templates}
              selectedTemplate={selectedTemplate}
              onOpenChange={(open) =>
                setOpenGroups((current) => {
                  if (current.has(group.id) === open) return current
                  const next = new Set(current)
                  if (open) next.add(group.id)
                  else next.delete(group.id)
                  return next
                })
              }
              onSelectTemplate={(templateId) =>
                setChosenTemplates((current) => ({ ...current, [group.id]: templateId }))
              }
            >
              {group.tools.map((tool) => (
                <li key={tool.id}>
                  <ToolCard
                    tool={tool}
                    busy={activeTool === tool.id}
                    disabled={busy}
                    isFiltered={activeFilter === tool.id}
                    onDownload={() =>
                      tool.id === RSM_JSON_TOOL.id
                        ? onDownload()
                        : onGenerate(tool.id, selectedTemplate)
                    }
                    onFilter={() => onFilter(activeFilter === tool.id ? 'all' : tool.id)}
                    onFocusField={onFocusField}
                  />
                </li>
              ))}

              {showGitHub && (
                <li>
                  <div className="tool-card">
                    <GitHubPublisher
                      defaultName={repositoryName}
                      disabled={busy}
                      initiallyOpen={Boolean(initialOpenGitHub)}
                      publishing={activeTool === GITHUB_PUBLISH_ID}
                      templateId={selectedTemplate}
                      workspaceId={workspaceId}
                      onError={onError}
                      onPublish={onPublishGitHub}
                    />
                  </div>
                </li>
              )}
            </ToolGroup>
          )
        })}

        {visibleGroups.length === 0 && (
          <p className="tools-empty">No tool matches “{toolSearch}”.</p>
        )}
      </div>

      <p className="temporary-note">
        Workspaces expire after 12 hours of inactivity. Download your RSM JSON before leaving.
      </p>
    </aside>
  )
}

function matchesToolSearch(query: string, ...values: string[]): boolean {
  return !query || values.some((value) => value.toLocaleLowerCase().includes(query))
}

function initialOpenGroups(reopenRepository: boolean): Set<GeneratorCategory> {
  let open = new Set<GeneratorCategory>(['repository'])

  try {
    const stored = window.sessionStorage.getItem(OPEN_GROUPS_STORAGE_KEY)
    if (stored) {
      const parsed: unknown = JSON.parse(stored)
      if (Array.isArray(parsed)) {
        open = new Set(
          parsed.filter((id): id is GeneratorCategory =>
            TOOL_GROUP_IDS.includes(id as GeneratorCategory),
          ),
        )
      }
    }
  } catch {
    // Fall back to the default group when storage is unavailable or malformed.
  }

  if (reopenRepository) open.add('repository')
  return open
}
