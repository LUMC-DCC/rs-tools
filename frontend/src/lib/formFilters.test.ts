import { describe, expect, it } from 'vitest'

import {
  filterSchema,
  matchingFieldNames,
  mergeVisibleData,
  pickVisibleData,
  topLevelFieldNames,
} from './formFilters'
import type { SmpSchema } from '../types'

describe('tool field filters', () => {
  it('derives unique top-level names and filters the schema', () => {
    const fields = [
      { path: '/project_name', label: 'Project name', description: '' },
      { path: '/authors/entries', label: 'Authors', description: '' },
      { path: '/authors', label: 'Authors', description: '' },
    ]
    const names = topLevelFieldNames(fields)
    const schema = filterSchema(
      {
        type: 'object',
        properties: { project_name: { type: 'string' }, authors: { type: 'object' }, license: {} },
        required: ['project_name', 'license'],
      },
      names,
    )

    expect(names).toEqual(['project_name', 'authors'])
    expect(Object.keys(schema.properties || {})).toEqual(['project_name', 'authors'])
    expect(schema.required).toEqual(['project_name'])
  })

  it('preserves hidden data while updating or removing visible fields', () => {
    const complete = { project_name: 'Before', license: 'MIT', authors: { entries: [] } }
    expect(pickVisibleData(complete, ['project_name'])).toEqual({ project_name: 'Before' })
    expect(mergeVisibleData(complete, { project_name: 'After' }, ['project_name'])).toEqual({
      project_name: 'After',
      license: 'MIT',
      authors: { entries: [] },
    })
    expect(mergeVisibleData(complete, {}, ['project_name'])).toEqual({
      license: 'MIT',
      authors: { entries: [] },
    })
  })
})

describe('matchingFieldNames', () => {
  const schema = {
    type: 'object',
    properties: {
      project_name: { type: 'string' },
      quality_tools: {
        type: 'object',
        properties: { formatter: { type: 'string' }, linter: { type: 'string' } },
      },
      authors: {
        type: 'object',
        properties: {
          entries: { type: 'array', items: { $ref: '#/$defs/person' } },
        },
      },
    },
    $defs: { person: { type: 'object', properties: { orcid: { type: 'string' } } } },
  } as SmpSchema

  it('returns everything when nothing is searched for', () => {
    expect(matchingFieldNames(schema, '  ')).toEqual([
      'project_name',
      'quality_tools',
      'authors',
    ])
  })

  it('matches a top-level name', () => {
    expect(matchingFieldNames(schema, 'project')).toEqual(['project_name'])
  })

  it('finds the top-level field a nested name belongs to', () => {
    // Searching for a nested field has to surface the field you would open to
    // reach it, not nothing.
    expect(matchingFieldNames(schema, 'formatter')).toEqual(['quality_tools'])
  })

  it('follows array items and local refs', () => {
    expect(matchingFieldNames(schema, 'orcid')).toEqual(['authors'])
  })

  it('ignores case', () => {
    expect(matchingFieldNames(schema, 'LINTER')).toEqual(['quality_tools'])
  })

  it('returns nothing when a search matches no field', () => {
    expect(matchingFieldNames(schema, 'nonsense')).toEqual([])
  })
})
