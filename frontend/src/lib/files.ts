import type { SmpData } from '../types'

export function smpFilename(data: SmpData): string {
  const candidate = typeof data.project_slug === 'string' ? data.project_slug : 'rsm'
  const safe = candidate
    .normalize('NFKD')
    .replace(/[^a-zA-Z0-9._-]+/g, '-')
    .replace(/^[.-]+|[.-]+$/g, '')
    .slice(0, 80)
  return `${safe || 'rsm'}.json`
}

export function saveBlob(blob: Blob, filename: string): void {
  const url = URL.createObjectURL(blob)
  const anchor = document.createElement('a')
  anchor.href = url
  anchor.download = filename
  document.body.appendChild(anchor)
  anchor.click()
  anchor.remove()
  URL.revokeObjectURL(url)
}
