import { useEffect, useState } from 'react'

import { ApiError, api } from '../api/client'
import type { GeneratorInfo, SmpSchema, Workspace } from '../types'

interface WorkspaceData {
  workspace: Workspace | null
  schema: SmpSchema | null
  generators: GeneratorInfo[]
  loading: boolean
  notFound: boolean
  error: string | null
  setWorkspace: (workspace: Workspace) => void
}

/**
 * Load everything the workspace view needs.
 *
 * The three requests are made together because the view cannot render usefully
 * without all of them, and an expired workspace is reported separately from a
 * failure: it has its own screen, and it is the expected end of a workspace's
 * life rather than something going wrong.
 */
export function useWorkspaceData(workspaceId: string): WorkspaceData {
  const [workspace, setWorkspace] = useState<Workspace | null>(null)
  const [schema, setSchema] = useState<SmpSchema | null>(null)
  const [generators, setGenerators] = useState<GeneratorInfo[]>([])
  const [loading, setLoading] = useState(true)
  const [notFound, setNotFound] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let active = true
    Promise.all([api.getWorkspace(workspaceId), api.getSchema(), api.getGenerators()])
      .then(([loadedWorkspace, loadedSchema, loadedGenerators]) => {
        if (!active) return
        setWorkspace(loadedWorkspace)
        setSchema(loadedSchema)
        setGenerators(loadedGenerators)
      })
      .catch((caught: unknown) => {
        if (!active) return
        if (caught instanceof ApiError && caught.status === 404) setNotFound(true)
        else setError(caught instanceof Error ? caught.message : 'Could not load this workspace.')
      })
      .finally(() => {
        if (active) setLoading(false)
      })
    return () => {
      active = false
    }
  }, [workspaceId])

  return { workspace, schema, generators, loading, notFound, error, setWorkspace }
}
