import { useCallback, useEffect, useState } from 'react'

import { api } from '../api/client'
import type { GitHubConnectionStatus } from '../types'

interface GitHubConnection {
  status: GitHubConnectionStatus | null
  connect: () => Promise<void>
  disconnect: () => void
  reload: () => void
  connecting: boolean
}

/**
 * Track whether this workspace currently holds a GitHub authorization.
 *
 * The connection lives in a cookie the browser cannot read, so its state is
 * only ever known by asking the server.
 */
export function useGitHubConnection(
  workspaceId: string,
  onError: (message: string) => void,
): GitHubConnection {
  const [status, setStatus] = useState<GitHubConnectionStatus | null>(null)
  const [connecting, setConnecting] = useState(false)

  const reload = useCallback(() => {
    let active = true
    api
      .getGitHubStatus(workspaceId)
      .then((loaded) => {
        if (active) setStatus(loaded)
      })
      .catch((caught: unknown) => {
        if (active) onError(message(caught, 'Could not check the GitHub connection.'))
      })
    return () => {
      active = false
    }
  }, [workspaceId, onError])

  useEffect(reload, [reload])

  const connect = useCallback(async () => {
    setConnecting(true)
    try {
      const result = await api.connectGitHub(workspaceId)
      // A full navigation, not a popup: the OAuth callback returns the browser
      // to this workspace with the connection cookie set.
      window.location.assign(result.authorization_url)
    } catch (caught) {
      onError(message(caught, 'Could not start the GitHub authorization.'))
      setConnecting(false)
    }
  }, [workspaceId, onError])

  const disconnect = useCallback(() => {
    api
      .disconnectGitHub(workspaceId)
      .then(reload)
      .catch((caught: unknown) => onError(message(caught, 'Could not disconnect GitHub.')))
  }, [workspaceId, onError, reload])

  return { status, connect, disconnect, reload, connecting }
}

function message(caught: unknown, fallback: string): string {
  return caught instanceof Error ? caught.message : fallback
}
