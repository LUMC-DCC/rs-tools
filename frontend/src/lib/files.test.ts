import { describe, expect, it } from 'vitest'

import { smpFilename } from './files'

describe('smpFilename', () => {
  it('sanitizes a project slug before using it as a download name', () => {
    expect(smpFilename({ project_slug: '../../Unsafe project' })).toBe('Unsafe-project.json')
  })

  it('uses a stable fallback', () => {
    expect(smpFilename({})).toBe('rsm.json')
  })
})
