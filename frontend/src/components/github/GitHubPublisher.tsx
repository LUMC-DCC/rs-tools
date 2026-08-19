import { CheckCircle2, ExternalLink } from 'lucide-react'
import { useEffect, useRef, useState } from 'react'

import GitHubIcon from '../common/GitHubIcon'
import { useGitHubConnection } from '../../hooks/useGitHubConnection'
import type { GitHubPublishResult, GitHubRepositoryOptions } from '../../types'

interface GitHubPublisherProps {
  defaultName: string
  disabled: boolean
  initiallyOpen: boolean
  publishing: boolean
  templateId?: string
  workspaceId: string
  onError: (message: string) => void
  onPublish: (options: GitHubRepositoryOptions) => Promise<GitHubPublishResult>
}

/** Create the generated repository directly on the user's GitHub account. */
export default function GitHubPublisher({
  defaultName,
  disabled,
  initiallyOpen,
  publishing,
  templateId,
  workspaceId,
  onError,
  onPublish,
}: GitHubPublisherProps) {
  const [open, setOpen] = useState(initiallyOpen)
  const { status, connect, disconnect, reload, connecting } = useGitHubConnection(
    workspaceId,
    onError,
  )
  const [owner, setOwner] = useState('')
  const [name, setName] = useState(defaultName)
  const [isPrivate, setIsPrivate] = useState(false)
  const [result, setResult] = useState<GitHubPublishResult | null>(null)
  const form = useRef<HTMLDivElement | null>(null)
  const landed = useRef(false)

  const selectedOwner = owner || status?.accounts[0]?.login || ''
  const connected = Boolean(status?.connected)

  // Coming back from GitHub, the browser lands at the top of the workspace while
  // the thing the person just authorized sits far down the tools panel. Bring
  // the form to them, and focus it, rather than leaving them to find it.
  //
  // Jumps rather than glides: the person has just been redirected back from
  // another site, so there is no on-screen continuity for an animation to
  // preserve, and an instant scroll applies immediately instead of depending on
  // an animation frame that a backgrounded tab never runs.
  useEffect(() => {
    if (!initiallyOpen || !connected || landed.current) return
    const target = form.current
    if (!target) return
    landed.current = true
    target.scrollIntoView({ block: 'center' })
    target.focus({ preventScroll: true })
  }, [initiallyOpen, connected])

  const publish = async () => {
    setResult(null)
    try {
      setResult(
        await onPublish({
          owner: selectedOwner,
          name,
          private: isPrivate,
          template: templateId,
        }),
      )
      // Publishing attempts to revoke the authorization, so the connection
      // state may change as a result of the action itself.
      reload()
    } catch (caught) {
      onError(caught instanceof Error ? caught.message : 'Could not create the repository.')
    }
  }

  return (
    <>
      <div className="tool-card-main">
        <button
          type="button"
          className="button button-tool tool-card-action"
          aria-expanded={open}
          disabled={disabled}
          onClick={() => setOpen((current) => !current)}
        >
          <GitHubIcon size={13} />
          <span className="tool-card-label">Create repository on GitHub</span>
        </button>
      </div>

      {open && (
        <div className="github-section">
          {!status ? (
            <p className="github-note">Checking the GitHub connection…</p>
          ) : !status.configured ? (
            <p className="github-note">
              GitHub publishing is not configured on this deployment. Download the repository
              instead.
            </p>
          ) : result ? (
            <div className="github-publisher">
              <div className="github-success" role="status">
                <CheckCircle2 size={18} aria-hidden="true" />
                <div>
                  <strong>Repository created.</strong>
                  <a
                    className="github-result"
                    href={result.url}
                    target="_blank"
                    rel="noreferrer"
                  >
                    Open {selectedOwner}/{name} on GitHub
                    <ExternalLink size={12} aria-hidden="true" />
                  </a>
                  <span className="github-success-note">
                    {result.authorization_revoked
                      ? 'GitHub access has been revoked.'
                      : 'Automatic revocation failed. Disconnect GitHub below to retry.'}
                  </span>
                </div>
              </div>

              {!result.authorization_revoked && (
                <button type="button" className="link-button" onClick={disconnect}>
                  Disconnect GitHub
                </button>
              )}
            </div>
          ) : !status.connected ? (
            <div className="github-actions">
              <p className="github-note">
                Connect GitHub to choose an account and create the repository. You can disconnect
                the connection when you are finished.
              </p>
              <button
                type="button"
                className="button button-github button-block"
                disabled={connecting || disabled}
                onClick={() => void connect()}
              >
                <GitHubIcon size={14} />
                {connecting ? 'Opening GitHub…' : 'Sign in with GitHub'}
              </button>
            </div>
          ) : (
            <div
              className={`github-publisher ${initiallyOpen && !result ? 'github-publisher-attention' : ''}`}
              ref={form}
              tabIndex={-1}
            >
              {initiallyOpen && !result && (
                <div className="github-connected" role="status">
                  <strong>GitHub authorized.</strong>
                  <span>Check the destination below, then create the repository.</span>
                </div>
              )}

              <label className="github-field">
                <span>Owner</span>
                <select value={selectedOwner} onChange={(event) => setOwner(event.target.value)}>
                  {status.accounts.map((account) => (
                    <option value={account.login} key={account.login}>
                      {account.login} (
                      {account.type === 'Organization' ? 'organization' : 'your account'})
                    </option>
                  ))}
                </select>
              </label>

              <label className="github-field">
                <span>Repository name</span>
                <input value={name} onChange={(event) => setName(event.target.value)} />
              </label>

              <label className="github-field">
                <span>Visibility</span>
                <select
                  value={isPrivate ? 'private' : 'public'}
                  onChange={(event) => setIsPrivate(event.target.value === 'private')}
                >
                  <option value="public">Public — anyone can read it</option>
                  <option value="private">Private — only you and the owner</option>
                </select>
              </label>

              <button
                type="button"
                className="button button-github button-block"
                disabled={publishing || disabled || !selectedOwner || !name.trim()}
                onClick={() => void publish()}
              >
                <GitHubIcon size={14} />
                {publishing ? 'Creating repository…' : 'Create repository'}
              </button>

              <button type="button" className="link-button" onClick={disconnect}>
                Disconnect GitHub
              </button>
            </div>
          )}
        </div>
      )}
    </>
  )
}
