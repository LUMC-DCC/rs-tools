import type { SmpData } from '../types'

/**
 * Parse text that must be a JSON object.
 *
 * `JSON.parse` accepts arrays, numbers, and `null` as valid documents, none of
 * which an RSM document can be, so the shape is checked here rather than
 * failing later against the schema.
 *
 * @throws SyntaxError when the text is not valid JSON, or not an object.
 */
export function parseDocument(text: string): SmpData {
  const parsed = JSON.parse(text) as unknown
  if (!parsed || Array.isArray(parsed) || typeof parsed !== 'object') {
    throw new SyntaxError('The RSM document must be a JSON object.')
  }
  return parsed as SmpData
}
