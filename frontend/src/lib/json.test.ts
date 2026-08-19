import { describe, expect, it } from 'vitest'

import { parseDocument } from './json'

describe('parseDocument', () => {
  it('accepts a JSON object', () => {
    expect(parseDocument('{"project_slug": "example"}')).toEqual({ project_slug: 'example' })
  })

  it.each(['[]', '"text"', '12', 'null'])('rejects %s, which JSON.parse would accept', (text) => {
    expect(() => parseDocument(text)).toThrow(SyntaxError)
  })

  it('rejects malformed JSON', () => {
    expect(() => parseDocument('{"unclosed":')).toThrow(SyntaxError)
  })
})
