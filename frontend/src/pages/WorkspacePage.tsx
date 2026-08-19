import {
  type CSSProperties,
  useCallback,
  useDeferredValue,
  useMemo,
  useRef,
  useState,
} from 'react'
import { Link, useParams, useSearchParams } from 'react-router-dom'

import { api } from '../api/client'
import BrandHeader from '../components/common/BrandHeader'
import CenteredState from '../components/common/CenteredState'
import ErrorNotice from '../components/common/ErrorNotice'
import ValidationToast from '../components/common/ValidationToast'
import ToolsPanel, { GITHUB_PUBLISH_ID } from '../components/tools/ToolsPanel'
import WorkspaceEditor, { type EditorMode } from '../components/workspace/WorkspaceEditor'
import WorkspaceResizer, { initialToolsPercent } from '../components/workspace/WorkspaceResizer'
import WorkspaceTitlebar from '../components/workspace/WorkspaceTitlebar'
import { useAutosave, useUnsavedChangesWarning } from '../hooks/useAutosave'
import { useStickyViewport } from '../hooks/useStickyViewport'
import { useWorkspaceData } from '../hooks/useWorkspaceData'
import { saveBlob, smpFilename } from '../lib/files'
import {
  filterSchema,
  mergeVisibleData,
  pickVisibleData,
  topLevelNames,
  visibleFields,
} from '../lib/formFilters'
import { parseDocument } from '../lib/json'
import { RSM_JSON_TOOL } from '../lib/toolGroups'
import type { GitHubPublishResult, GitHubRepositoryOptions, SmpData, Workspace } from '../types'

export default function WorkspacePage() {
  const { workspaceId = '' } = useParams()
  const [searchParams] = useSearchParams()
  const { workspace, schema, generators, loading, notFound, error: loadError, setWorkspace } =
    useWorkspaceData(workspaceId)

  // The document being edited. Null until the first edit, when the loaded
  // workspace still is the document.
  const [draft, setDraft] = useState<SmpData | null>(null)
  // A text buffer, held only while the raw editor is open and the text may not
  // yet parse.
  const [rawText, setRawText] = useState<string | null>(null)
  const [mode, setMode] = useState<EditorMode>('form')
  const [fieldFilter, setFieldFilter] = useState('all')
  const [search, setSearch] = useState('')
  // Typing filters the whole form, so the rebuild trails the keystrokes rather
  // than blocking them.
  const deferredSearch = useDeferredValue(search)
  // One tool runs at a time, so one piece of state says which. Separate
  // "downloading" and "generating" flags would only be able to disagree.
  const [activeTool, setActiveTool] = useState<string | null>(null)
  const [toolsPercent, setToolsPercent] = useState(initialToolsPercent)
  const [resizingTools, setResizingTools] = useState(false)
  const workspaceGrid = useRef<HTMLDivElement | null>(null)

  // A save only reports back when nothing newer has been typed, so adopting the
  // stored document here is what keeps the two editors agreeing: an edit made
  // as raw JSON has to become the document the form and the tools work from.
  const onSaved = useCallback(
    (updated: Workspace) => {
      setWorkspace(updated)
      setDraft(updated.data)
    },
    [setWorkspace],
  )
  const autosave = useAutosave(workspaceId, onSaved)
  useUnsavedChangesWarning(autosave.saveState)
  useStickyViewport(workspaceGrid, !loading)

  // Memoized because several hooks below take it as a dependency; a fresh
  // object each render would make every one of them recompute on every render.
  const data = useMemo(() => draft ?? workspace?.data ?? {}, [draft, workspace])
  const rawSource = rawText ?? JSON.stringify(data, null, 2)

  const applyFormData = (next: SmpData) => {
    setDraft(next)
    autosave.schedule(next)
  }

  /**
   * The document as it stands in whichever editor is open.
   *
   * Raw JSON is only parsed at the moment it is needed, so a half-typed
   * document does not interrupt editing.
   */
  const currentData = (): SmpData => (mode === 'form' ? data : parseDocument(rawSource))

  /**
   * Store the pending edit, then run a tool against what was stored.
   *
   * The server generates from the stored document, so the edit has to land
   * first. Each stage reports its own failure: an unparseable document is the
   * document's problem, a rejected save is already reported by the autosave
   * hook, and anything after that is the tool's problem and must not be
   * reported as the document being unsaved.
   */
  const runWithSavedDocument = async (
    toolId: string,
    perform: (saved: Workspace) => Promise<void>,
  ) => {
    setActiveTool(toolId)
    try {
      let document: SmpData
      try {
        document = currentData()
      } catch (caught) {
        autosave.reportInvalid(
          caught instanceof Error ? caught.message : 'The raw JSON is not valid.',
        )
        return
      }

      let saved: Workspace
      try {
        saved = await autosave.saveNow(document)
      } catch {
        return
      }

      await perform(saved)
    } catch (caught) {
      autosave.reportProblem(
        caught instanceof Error ? caught.message : 'That action could not be completed.',
      )
    } finally {
      setActiveTool(null)
    }
  }

  const handleDownloadWorkspace = () =>
    runWithSavedDocument(RSM_JSON_TOOL.id, (saved) => {
      const blob = new Blob([JSON.stringify(saved.data, null, 2) + '\n'], {
        type: 'application/json',
      })
      saveBlob(blob, smpFilename(saved.data))
      return Promise.resolve()
    })

  const handleGenerate = (toolId: string, templateId?: string) =>
    runWithSavedDocument(toolId, async () => {
      const artifact = await api.downloadGenerator(workspaceId, toolId, templateId)
      saveBlob(artifact.blob, artifact.filename)
    })

  const handleGitHubPublish = async (
    options: GitHubRepositoryOptions,
  ): Promise<GitHubPublishResult> => {
    setActiveTool(GITHUB_PUBLISH_ID)
    try {
      await autosave.saveNow(currentData())
      return await api.publishGitHubRepository(workspaceId, options)
    } finally {
      setActiveTool(null)
    }
  }

  /** Move the raw document into the form, reporting invalid JSON rather than losing it. */
  const adoptRawDocument = (): boolean => {
    try {
      const parsed = parseDocument(rawSource)
      setDraft(parsed)
      setRawText(null)
      setMode('form')
      autosave.schedule(parsed)
      return true
    } catch (caught) {
      autosave.reportInvalid(
        caught instanceof Error ? caught.message : 'The raw JSON is not valid.',
      )
      return false
    }
  }

  const switchMode = (next: EditorMode) => {
    autosave.clearFeedback()
    if (next === 'json') {
      setRawText(JSON.stringify(data, null, 2))
      setMode('json')
      return
    }
    adoptRawDocument()
  }

  const focusSchemaField = (path: string) => {
    if (mode === 'json' && !adoptRawDocument()) return

    // A field hidden by the filter or the search cannot be focused, so whatever
    // is hiding it is cleared rather than scrolling to nothing.
    const topLevelName = path.split('/').filter(Boolean)[0]
    if (topLevelName && !visibleFieldNames.includes(topLevelName)) {
      setFieldFilter('all')
      setSearch('')
    }

    const elementId = `root_${path
      .split('/')
      .filter(Boolean)
      .map((part) => part.replaceAll('~1', '/').replaceAll('~0', '~'))
      .join('_')}`
    const revealAndFocus = () => {
      const field = document.getElementById(elementId)
      if (!field) return

      // Array entries share their disclosure state. Opening the closed entry
      // through its summary lets that state update normally, which expands all
      // sibling entries before attempting to focus the invalid control.
      const closedEntry = field.closest<HTMLDetailsElement>(
        'details.array-entry-details:not([open])',
      )
      if (closedEntry) {
        closedEntry.querySelector<HTMLElement>('summary')?.click()
        window.setTimeout(revealAndFocus, 0)
        return
      }

      // `scrollIntoView()` does not account for the sticky metadata toolbar,
      // so a field near the top of the viewport could otherwise finish hidden
      // behind it. Position the field just below the live toolbar height.
      const toolbarBottom = document
        .querySelector<HTMLElement>('.editor-toolbar')
        ?.getBoundingClientRect().bottom
      window.scrollBy({
        top: field.getBoundingClientRect().top - ((toolbarBottom ?? 0) + 16),
        behavior: 'smooth',
      })
      const focusTarget = field.matches('input, textarea, select, button')
        ? field
        : field.querySelector<HTMLElement>('input, textarea, select, button')
      focusTarget?.focus({ preventScroll: true })
    }

    // Deferred so the form has re-rendered with the field visible.
    window.setTimeout(revealAndFocus, 0)
  }

  const title = useMemo(() => {
    const projectName = data.project_name
    return typeof projectName === 'string' && projectName.trim()
      ? projectName
      : 'Untitled software project'
  }, [data.project_name])

  // Not memoized: reading the top-level property names is a handful of string
  // comparisons, and the one costly path — walking the schema for a search —
  // only runs while a search is active, on a deferred value.
  const activeGenerator = generators.find((generator) => generator.id === fieldFilter)
  const visibleFieldNames = visibleFields(schema, activeGenerator?.fields ?? null, deferredSearch)
  // True when a filter or a search is hiding part of the document. When nothing
  // is hidden the schema passes through untouched, so the form is not rebuilt.
  const narrowed = schema ? visibleFieldNames.length !== topLevelNames(schema).length : false

  const displayedSchema = useMemo(
    () => (narrowed ? filterSchema(schema ?? {}, visibleFieldNames) : schema),
    [narrowed, schema, visibleFieldNames],
  )
  const displayedData = useMemo(
    () => (narrowed ? pickVisibleData(data, visibleFieldNames) : data),
    [narrowed, data, visibleFieldNames],
  )

  if (loading) {
    return (
      <CenteredState title="Opening workspace…" leading={<div className="loading-mark" />} />
    )
  }

  if (notFound) {
    return (
      <CenteredState title="Workspace unavailable">
        <p>This workspace has expired, or never existed.</p>
        <Link className="button button-primary" to="/">
          Create a new workspace
        </Link>
      </CenteredState>
    )
  }

  if (!workspace || !schema) {
    return (
      <CenteredState title="This workspace could not be opened">
        <ErrorNotice message={loadError || 'Could not load this workspace.'} />
        <Link className="button button-muted" to="/">
          Return home
        </Link>
      </CenteredState>
    )
  }

  return (
    <div className="app-shell">
      <BrandHeader />
      <main className="workspace-main">
        <WorkspaceTitlebar title={title} saveState={autosave.saveState} />

        <div
          className={`workspace-grid ${resizingTools ? 'is-resizing' : ''}`}
          ref={workspaceGrid}
          style={{ '--tools-panel-width': `${toolsPercent}%` } as CSSProperties}
        >
          <WorkspaceEditor
            data={displayedData}
            fieldFilter={fieldFilter}
            generators={generators}
            mode={mode}
            rawText={rawSource}
            schema={displayedSchema || schema}
            search={search}
            visibleFieldCount={visibleFieldNames.length}
            narrowed={narrowed}
            onFieldFilterChange={setFieldFilter}
            onSearchChange={setSearch}
            onFormChange={(visibleUpdate) =>
              applyFormData(
                narrowed
                  ? mergeVisibleData(data, visibleUpdate, visibleFieldNames)
                  : visibleUpdate,
              )
            }
            onModeChange={switchMode}
            onRawTextChange={(text) => {
              setRawText(text)
              autosave.scheduleRaw(text)
            }}
          />

          <WorkspaceResizer
            gridRef={workspaceGrid}
            toolsPercent={toolsPercent}
            onChange={setToolsPercent}
            onResizeStateChange={setResizingTools}
          />

          <ToolsPanel
            activeFilter={fieldFilter}
            activeTool={activeTool}
            generators={generators}
            initialOpenGitHub={searchParams.get('github') === 'connected'}
            preferredTemplate={typeof data.language === 'string' ? data.language : undefined}
            repositoryName={
              typeof data.project_slug === 'string' && data.project_slug.trim()
                ? data.project_slug
                : 'research-software'
            }
            workspaceId={workspaceId}
            onDownload={() => void handleDownloadWorkspace()}
            onError={autosave.reportProblem}
            onFilter={(toolId) => {
              if (mode === 'json') switchMode('form')
              setFieldFilter(toolId)
              window.scrollTo({ top: 0, behavior: 'smooth' })
            }}
            onGenerate={(toolId, templateId) => void handleGenerate(toolId, templateId)}
            onFocusField={focusSchemaField}
            onPublishGitHub={handleGitHubPublish}
          />
        </div>
      </main>

      {autosave.error && (
        <ValidationToast
          message={autosave.error}
          issues={autosave.issues}
          onDismiss={autosave.clearFeedback}
          onFocusField={focusSchemaField}
        />
      )}
    </div>
  )
}
