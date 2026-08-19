import type { RJSFSchema } from '@rjsf/utils'

/** An RSM document. Its shape is the published JSON Schema, not a type here. */
export type SmpData = Record<string, unknown>

/** The schema, as served by `GET /api/schema`. */
export type SmpSchema = RJSFSchema

export interface Workspace {
  id: string
  data: SmpData
  created_at: string
  updated_at: string
}

export interface ValidationIssue {
  /** JSON Pointer to the offending value, or `$` for the document root. */
  path: string
  message: string
  validator?: string | null
}

export interface ApiErrorBody {
  detail?: string
  errors?: ValidationIssue[]
}

export interface GeneratorField {
  path: string
  label: string
  description: string
}

export interface GeneratorTemplate {
  id: string
  label: string
}

/** How a generated artifact is grouped in the tools panel. */
export type GeneratorCategory = 'metadata' | 'documentation' | 'project' | 'repository'

/** One generator, as described by `GET /api/generators`. */
export interface GeneratorInfo {
  id: string
  /** The name of the thing produced, such as `CITATION.cff`. */
  label: string
  description: string
  filename: string
  category: GeneratorCategory
  fields: GeneratorField[]
  templates: GeneratorTemplate[]
}

/**
 * One button in the tools panel.
 *
 * Not every tool is a generator: the RSM document itself is downloaded from the
 * workspace, so the panel works from this shape instead of from GeneratorInfo.
 */
export interface ToolItem {
  id: string
  /** The full action, as written on the button: "Download CITATION.cff". */
  action: string
  filename: string
  description: string
  fields: GeneratorField[]
  templates: GeneratorTemplate[]
}

export interface ToolGroup {
  id: GeneratorCategory
  title: string
  description: string
  tools: ToolItem[]
}

export interface ArtifactDownload {
  blob: Blob
  filename: string
}

export interface GitHubAccount {
  login: string
  type: 'User' | 'Organization'
}

export interface GitHubConnectionStatus {
  configured: boolean
  connected: boolean
  accounts: GitHubAccount[]
}

export interface GitHubRepositoryOptions {
  owner: string
  name: string
  private: boolean
  template?: string
}

export interface GitHubPublishResult {
  url: string
  authorization_revoked: boolean
}
