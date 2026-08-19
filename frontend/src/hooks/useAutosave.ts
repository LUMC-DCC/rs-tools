import { useCallback, useEffect, useRef, useState } from 'react'

import { ApiError, api } from '../api/client'
import { parseDocument } from '../lib/json'
import type { SmpData, ValidationIssue, Workspace } from '../types'

export type SaveState = 'idle' | 'dirty' | 'saving' | 'saved' | 'invalid' | 'error'

const AUTOSAVE_DELAY_MS = 800
const SAVED_BADGE_MS = 1800

interface Autosave {
  saveState: SaveState
  error: string | null
  issues: ValidationIssue[] | undefined
  /** Queue a save after the usual debounce. */
  schedule: (data: SmpData) => void
  /** Queue a save of raw text, parsed only once typing has stopped. */
  scheduleRaw: (text: string) => void
  /** Save straight away and wait for the result, for actions that need the stored document. */
  saveNow: (data: SmpData) => Promise<Workspace>
  /** Report unparseable input: shows the message and marks the document invalid. */
  reportInvalid: (message: string) => void
  /**
   * Report a failure that is not about saving.
   *
   * Deliberately leaves `saveState` alone: a generator or GitHub call can fail
   * long after the document was stored, and showing "Not saved" then would be a
   * lie about where the user's work is.
   */
  reportProblem: (message: string) => void
  clearFeedback: () => void
}

/**
 * Save edits automatically, a short pause after typing stops.
 *
 * Two problems make this more than a debounce. Saves must not overtake each
 * other, so they run through a promise queue and the workspace always ends up
 * matching the last edit rather than whichever request finished last. And a
 * response that arrives after the user has typed again must not overwrite what
 * they are now editing, so each edit takes a revision number and a response is
 * only applied if its revision is still current.
 */
export function useAutosave(
  workspaceId: string,
  onSaved: (workspace: Workspace) => void,
): Autosave {
  const [saveState, setSaveState] = useState<SaveState>('idle')
  const [error, setError] = useState<string | null>(null)
  const [issues, setIssues] = useState<ValidationIssue[] | undefined>()

  const autosaveTimer = useRef<number | undefined>(undefined)
  const savedTimer = useRef<number | undefined>(undefined)
  const revision = useRef(0)
  const queue = useRef<Promise<unknown>>(Promise.resolve())

  useEffect(
    () => () => {
      window.clearTimeout(autosaveTimer.current)
      window.clearTimeout(savedTimer.current)
    },
    [],
  )

  const clearFeedback = useCallback(() => {
    setError(null)
    setIssues(undefined)
  }, [])

  const save = useCallback(
    (data: SmpData, editRevision: number): Promise<Workspace> => {
      const operation = queue.current
        .catch(() => undefined)
        .then(async () => {
          const isCurrent = () => editRevision === revision.current
          if (isCurrent()) setSaveState('saving')
          try {
            const updated = await api.replaceWorkspace(workspaceId, data)
            if (isCurrent()) {
              onSaved(updated)
              clearFeedback()
              setSaveState('saved')
              window.clearTimeout(savedTimer.current)
              savedTimer.current = window.setTimeout(() => {
                if (isCurrent()) setSaveState('idle')
              }, SAVED_BADGE_MS)
            }
            return updated
          } catch (caught) {
            if (isCurrent()) {
              if (caught instanceof ApiError) setIssues(caught.issues)
              setError(caught instanceof Error ? caught.message : 'Could not save your changes.')
              setSaveState('error')
            }
            throw caught
          }
        })

      queue.current = operation.catch(() => undefined)
      return operation
    },
    [workspaceId, onSaved, clearFeedback],
  )

  const beginEdit = useCallback(() => {
    window.clearTimeout(autosaveTimer.current)
    window.clearTimeout(savedTimer.current)
    setError(null)
    setIssues(undefined)
    setSaveState('dirty')
    return ++revision.current
  }, [])

  const schedule = useCallback(
    (data: SmpData) => {
      const editRevision = beginEdit()
      autosaveTimer.current = window.setTimeout(() => {
        void save(data, editRevision).catch(() => undefined)
      }, AUTOSAVE_DELAY_MS)
    },
    [beginEdit, save],
  )

  const scheduleRaw = useCallback(
    (text: string) => {
      const editRevision = beginEdit()
      autosaveTimer.current = window.setTimeout(() => {
        // Parsed here, not on every keystroke: a half-typed document is not a
        // mistake, it is someone still typing.
        try {
          void save(parseDocument(text), editRevision).catch(() => undefined)
        } catch (caught) {
          if (editRevision !== revision.current) return
          setError(caught instanceof Error ? caught.message : 'The raw JSON is not valid.')
          setSaveState('invalid')
        }
      }, AUTOSAVE_DELAY_MS)
    },
    [beginEdit, save],
  )

  const saveNow = useCallback(
    (data: SmpData) => {
      window.clearTimeout(autosaveTimer.current)
      return save(data, ++revision.current)
    },
    [save],
  )

  const reportInvalid = useCallback((invalidMessage: string) => {
    setError(invalidMessage)
    setSaveState('invalid')
  }, [])

  const reportProblem = useCallback((problemMessage: string) => {
    setError(problemMessage)
  }, [])

  return {
    saveState,
    error,
    issues,
    schedule,
    scheduleRaw,
    saveNow,
    reportInvalid,
    reportProblem,
    clearFeedback,
  }
}

/** Warn before leaving while an edit has not reached the server. */
export function useUnsavedChangesWarning(saveState: SaveState): void {
  useEffect(() => {
    const unsaved = ['dirty', 'saving', 'invalid', 'error'].includes(saveState)
    if (!unsaved) return
    const warn = (event: BeforeUnloadEvent) => {
      event.preventDefault()
      event.returnValue = ''
    }
    window.addEventListener('beforeunload', warn)
    return () => window.removeEventListener('beforeunload', warn)
  }, [saveState])
}
