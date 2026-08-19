import type { RJSFSchema } from '@rjsf/utils'

import { arrayItems, resolveLocalRef, subschemas } from './schema'
import type { GeneratorField, SmpData, SmpSchema } from '../types'

/** Every top-level property, in schema order. */
export function topLevelNames(schema: SmpSchema): string[] {
  return Object.keys(schema.properties ?? {})
}

/**
 * The top-level fields the form should show.
 *
 * The tool filter and the search each narrow the same list, so they compose:
 * searching inside a filtered form searches what is on screen. Neither removes
 * anything from the document, only from view.
 */
export function visibleFields(
  schema: SmpSchema | null,
  generatorFields: GeneratorField[] | null,
  search: string,
): string[] {
  if (!schema) return []
  const byFilter = generatorFields ? topLevelFieldNames(generatorFields) : topLevelNames(schema)
  const needle = search.trim()
  if (!needle) return byFilter
  const found = new Set(matchingFieldNames(schema, needle))
  return byFilter.filter((name) => found.has(name))
}

/**
 * Top-level fields matching a search, including by their nested field names.
 *
 * Searching for `formatter` has to find `quality_tools`, because that is the
 * field you would have to open to reach it. Matching is on the schema's own
 * property names, which are exactly what the form displays, so what you type is
 * what you see.
 */
export function matchingFieldNames(schema: SmpSchema, query: string): string[] {
  const needle = query.trim().toLowerCase()
  if (!needle) return topLevelNames(schema)
  return Object.entries(subschemas(schema))
    .filter(([name, property]) => matches(name, property, schema, needle, 0))
    .map(([name]) => name)
}

function matches(
  name: string,
  property: RJSFSchema,
  root: RJSFSchema,
  needle: string,
  depth: number,
): boolean {
  if (name.toLowerCase().includes(needle)) return true
  // Bounded rather than cycle-tracked: RSM nests a handful of levels, and a
  // depth limit is the simpler guard against a self-referencing `$ref`.
  if (depth > 6) return false
  const field = resolveLocalRef(property, root)
  const items = arrayItems(field)
  if (items && matches('', items, root, needle, depth + 1)) return true
  return Object.entries(subschemas(field)).some(([childName, child]) =>
    matches(childName, child, root, needle, depth + 1),
  )
}

export function topLevelFieldNames(fields: GeneratorField[]): string[] {
  return fields
    .map((field) => field.path.split('/').filter(Boolean)[0])
    .filter((name, index, names): name is string => Boolean(name) && names.indexOf(name) === index)
}

export function filterSchema(schema: SmpSchema, fieldNames: string[]): RJSFSchema {
  const allowed = new Set(fieldNames)
  const properties = Object.fromEntries(
    Object.entries(schema.properties || {}).filter(([name]) => allowed.has(name)),
  )
  const required = Array.isArray(schema.required)
    ? schema.required.filter((name): name is string => typeof name === 'string' && allowed.has(name))
    : undefined

  return {
    ...schema,
    properties,
    required,
  }
}

export function pickVisibleData(data: SmpData, fieldNames: string[]): SmpData {
  const visible = new Set(fieldNames)
  return Object.fromEntries(Object.entries(data).filter(([name]) => visible.has(name)))
}

export function mergeVisibleData(
  current: SmpData,
  visibleUpdate: SmpData,
  fieldNames: string[],
): SmpData {
  const merged = { ...current }
  for (const name of fieldNames) {
    if (name in visibleUpdate) merged[name] = visibleUpdate[name]
    else delete merged[name]
  }
  return merged
}
