import { describe, expect, it } from 'vitest'

import { resolveTheme } from './theme'

describe('resolveTheme', () => {
  it('follows the system preference in auto mode', () => {
    expect(resolveTheme('auto', false)).toBe('light')
    expect(resolveTheme('auto', true)).toBe('dark')
  })

  it('keeps an explicit preference', () => {
    expect(resolveTheme('light', true)).toBe('light')
    expect(resolveTheme('dark', false)).toBe('dark')
  })
})
