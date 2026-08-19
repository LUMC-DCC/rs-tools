import { type ChangeEvent, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'

import { ApiError, api } from '../api/client'
import BrandHeader from '../components/common/BrandHeader'
import ErrorNotice from '../components/common/ErrorNotice'
import type { SmpData, ValidationIssue } from '../types'

const exampleDocument = `{
  "project_slug": "my-research-software",
  "project_name": "My research software"
}`

export default function HomePage() {
  const navigate = useNavigate()
  const fileInput = useRef<HTMLInputElement>(null)
  const [showImport, setShowImport] = useState(false)
  const [source, setSource] = useState(exampleDocument)
  const [busy, setBusy] = useState<'empty' | 'import' | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [issues, setIssues] = useState<ValidationIssue[] | undefined>()

  const clearError = () => {
    setError(null)
    setIssues(undefined)
  }

  const createEmpty = async () => {
    setBusy('empty')
    clearError()
    try {
      const workspace = await api.createEmptyWorkspace()
      void navigate(`/w/${workspace.id}`)
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'Could not create a workspace.')
    } finally {
      setBusy(null)
    }
  }

  const createFromData = async () => {
    setBusy('import')
    clearError()
    try {
      const parsed = JSON.parse(source) as unknown
      if (!parsed || Array.isArray(parsed) || typeof parsed !== 'object') {
        throw new Error('The RSM document must be a JSON object.')
      }
      const workspace = await api.createWorkspace(parsed as SmpData)
      void navigate(`/w/${workspace.id}`)
    } catch (caught) {
      if (caught instanceof ApiError) setIssues(caught.issues)
      setError(caught instanceof Error ? caught.message : 'Could not import this document.')
    } finally {
      setBusy(null)
    }
  }

  const readFile = async (event: ChangeEvent<HTMLInputElement>) => {
    clearError()
    const file = event.target.files?.[0]
    if (!file) return
    event.target.value = ''
    if (file.size > 1_048_576) {
      setError('Choose a JSON document smaller than 1 MB.')
      return
    }
    try {
      setSource(await file.text())
      setShowImport(true)
    } catch {
      setError('The selected file could not be read.')
    }
  }

  return (
    <div className="app-shell">
      <BrandHeader />
      <main className="home-main">
        <section className="panel start-panel">
          <h1>Create a workspace</h1>
          <p className="intro">
            Create a temporary workspace to edit Research Software Management metadata and
            download the result.
          </p>

          {!showImport && error && <ErrorNotice message={error} />}

          <div className="start-actions">
            <button
              className="button button-primary"
              type="button"
              onClick={() => void createEmpty()}
              disabled={busy !== null}
            >
              {busy === 'empty' ? 'Creating…' : 'Create empty workspace'}
            </button>
            <button
              className="button button-muted"
              type="button"
              onClick={() => {
                setShowImport((visible) => !visible)
                clearError()
              }}
              disabled={busy !== null}
              aria-expanded={showImport}
            >
              {showImport ? 'Cancel import' : 'Create workspace from data'}
            </button>
          </div>

          <p className="temporary-note">
            Workspaces are temporary and expire automatically after 12 hours of inactivity.
          </p>

          {showImport && (
            <div className="import-section">
              <h2>Import RSM data</h2>
              <p>Paste a JSON document or choose a file.</p>
              {error && <ErrorNotice message={error} issues={issues} />}
              <label className="field-label" htmlFor="smp-json">
                RSM JSON
              </label>
              <textarea
                id="smp-json"
                className="json-editor"
                value={source}
                onChange={(event) => setSource(event.target.value)}
                spellCheck={false}
                rows={12}
              />
              <div className="import-actions">
                <input
                  ref={fileInput}
                  className="visually-hidden"
                  type="file"
                  accept="application/json,.json"
                  onChange={(event) => void readFile(event)}
                />
                <button
                  className="button button-muted"
                  type="button"
                  onClick={() => fileInput.current?.click()}
                >
                  Choose JSON file
                </button>
                <button
                  className="button button-primary"
                  type="button"
                  onClick={() => void createFromData()}
                  disabled={busy !== null}
                >
                  {busy === 'import' ? 'Validating…' : 'Create workspace'}
                </button>
              </div>
            </div>
          )}
        </section>
      </main>
    </div>
  )
}
