import type {
  ApiErrorBody,
  ArtifactDownload,
  GeneratorInfo,
  GitHubConnectionStatus,
  GitHubPublishResult,
  GitHubRepositoryOptions,
  SmpData,
  SmpSchema,
  Workspace,
} from '../types'

/**
 * A failed API response.
 *
 * The server writes its messages for the person reading them, so `message` is
 * shown as-is. `issues` carries the JSON Pointer paths of a schema failure,
 * which is what lets the interface link to the offending field.
 */
export class ApiError extends Error {
  readonly status: number
  readonly issues: ApiErrorBody['errors']

  constructor(status: number, body: ApiErrorBody) {
    super(body.detail || `The request failed (${status}).`)
    this.name = 'ApiError'
    this.status = status
    this.issues = body.errors
  }
}

/** Throw an ApiError for any non-success response, keeping the server's own message. */
async function ensureOk(response: Response): Promise<Response> {
  if (response.ok) return response
  let body: ApiErrorBody = {}
  try {
    body = (await response.json()) as ApiErrorBody
  } catch {
    body = { detail: `The request failed (${response.status}).` }
  }
  throw new ApiError(response.status, body)
}

async function requestJson<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await ensureOk(await fetch(path, init))
  return (await response.json()) as T
}

function jsonRequest(method: string, data?: unknown): RequestInit {
  return {
    method,
    headers: data === undefined ? undefined : { 'Content-Type': 'application/json' },
    body: data === undefined ? undefined : JSON.stringify(data),
  }
}

/** Read the filename the server chose, rather than inventing one client-side. */
function attachmentFilename(response: Response, fallback: string): string {
  const disposition = response.headers.get('Content-Disposition') || ''
  return disposition.match(/filename="?([^";]+)"?/i)?.[1] || fallback
}

function workspacePath(workspaceId: string, suffix = ''): string {
  return `/api/workspaces/${encodeURIComponent(workspaceId)}${suffix}`
}

/** The only place in the application that talks to the API. */
export const api = {
  createEmptyWorkspace: () => requestJson<Workspace>('/api/workspaces/empty', jsonRequest('POST')),

  createWorkspace: (data: SmpData) =>
    requestJson<Workspace>('/api/workspaces', jsonRequest('POST', data)),

  getWorkspace: (workspaceId: string) => requestJson<Workspace>(workspacePath(workspaceId)),

  replaceWorkspace: (workspaceId: string, data: SmpData) =>
    requestJson<Workspace>(workspacePath(workspaceId), jsonRequest('PUT', data)),

  getSchema: () => requestJson<SmpSchema>('/api/schema'),

  getGenerators: () => requestJson<GeneratorInfo[]>('/api/generators'),

  downloadGenerator: async (
    workspaceId: string,
    generatorId: string,
    templateId?: string,
  ): Promise<ArtifactDownload> => {
    const query = templateId ? `?template=${encodeURIComponent(templateId)}` : ''
    const response = await ensureOk(
      await fetch(
        workspacePath(workspaceId, `/generators/${encodeURIComponent(generatorId)}${query}`),
      ),
    )
    return { blob: await response.blob(), filename: attachmentFilename(response, generatorId) }
  },

  getGitHubStatus: (workspaceId: string) =>
    requestJson<GitHubConnectionStatus>(workspacePath(workspaceId, '/github')),

  connectGitHub: (workspaceId: string) =>
    requestJson<{ authorization_url: string }>(workspacePath(workspaceId, '/github/connect'), {
      method: 'POST',
    }),

  disconnectGitHub: async (workspaceId: string): Promise<void> => {
    await ensureOk(await fetch(workspacePath(workspaceId, '/github'), { method: 'DELETE' }))
  },

  publishGitHubRepository: (workspaceId: string, options: GitHubRepositoryOptions) =>
    requestJson<GitHubPublishResult>(
      workspacePath(workspaceId, '/github/repositories'),
      jsonRequest('POST', options),
    ),
}
