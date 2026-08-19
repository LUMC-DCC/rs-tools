import type { RJSFSchema } from '@rjsf/utils'

/**
 * Small helpers for walking the RSM schema.
 *
 * Shared by the form's presentation rules and by field search, so both read the
 * schema the same way and neither carries its own copy of `$ref` handling.
 */

/** Resolve local references and `allOf` inheritance used by the schema.
 *
 * A specialised record can inherit a field from a shared definition and add a
 * constraint of its own (for example, require at least one selected role).
 * Presentation needs the combined shape to recognise that the inherited array
 * still has enum choices.
 */
export function resolveLocalRef(schema: RJSFSchema, root: RJSFSchema): RJSFSchema {
  return resolveSchema(schema, root, new Set())
}

function resolveSchema(
  schema: RJSFSchema,
  root: RJSFSchema,
  seenRefs: ReadonlySet<string>,
): RJSFSchema {
  let local = schema
  if (schema.$ref?.startsWith('#/')) {
    if (seenRefs.has(schema.$ref)) return schema
    let current: unknown = root
    for (const encodedPart of schema.$ref.slice(2).split('/')) {
      const part = encodedPart.replaceAll('~1', '/').replaceAll('~0', '~')
      if (!current || typeof current !== 'object') return schema
      current = (current as Record<string, unknown>)[part]
    }
    if (!current || typeof current !== 'object') return schema
    const { $ref: _ref, ...overrides } = schema
    local = mergeSchemas(
      resolveSchema(current, root, new Set([...seenRefs, schema.$ref])),
      overrides,
    )
  }

  const { allOf, ...base } = local
  if (!Array.isArray(allOf)) return base
  const inherited = allOf.reduce<RJSFSchema>(
    (combined, branch) =>
      typeof branch === 'object' && branch !== null
        ? mergeSchemas(combined, resolveSchema(branch, root, seenRefs))
        : combined,
    {},
  )
  return mergeSchemas(inherited, base)
}

/** Merge the schema keywords that describe a field's visible structure. */
function mergeSchemas(base: RJSFSchema, extension: RJSFSchema): RJSFSchema {
  const result: RJSFSchema = { ...base, ...extension }
  if (base.properties || extension.properties) {
    const names = new Set([...Object.keys(base.properties ?? {}), ...Object.keys(extension.properties ?? {})])
    result.properties = Object.fromEntries(
      [...names].flatMap((name) => {
        const inherited = base.properties?.[name]
        const override = extension.properties?.[name]
        if (
          inherited &&
          override &&
          typeof inherited === 'object' &&
          typeof override === 'object'
        ) {
          return [[name, mergeSchemas(inherited, override)]]
        }
        const property = override ?? inherited
        return property === undefined ? [] : [[name, property]]
      }),
    )
  }
  if (base.required || extension.required) {
    result.required = [...new Set([...(base.required ?? []), ...(extension.required ?? [])])]
  }
  if (
    base.items &&
    extension.items &&
    !Array.isArray(base.items) &&
    !Array.isArray(extension.items) &&
    typeof base.items === 'object' &&
    typeof extension.items === 'object'
  ) {
    result.items = mergeSchemas(base.items, extension.items)
  }
  return result
}

/**
 * Read a node's properties as schemas.
 *
 * JSON Schema allows a boolean in place of a subschema. Those carry no title
 * and no children, so there is nothing to read from them and they are dropped
 * rather than special-cased at every use.
 */
export function subschemas(node: RJSFSchema): Record<string, RJSFSchema> {
  return Object.fromEntries(
    Object.entries(node.properties ?? {}).filter(
      (entry): entry is [string, RJSFSchema] => typeof entry[1] === 'object' && entry[1] !== null,
    ),
  )
}

/** The item schema of an array, or undefined for anything else. */
export function arrayItems(node: RJSFSchema): RJSFSchema | undefined {
  const { items } = node
  if (!items || Array.isArray(items) || typeof items !== 'object') return undefined
  return items
}

/** Whether a node is an array whose items are a fixed set of choices.
 *
 * Schemas are free to put the item enum behind a local `$ref`; resolve both
 * layers so a checklist is selected from its shape rather than one particular
 * spelling of that shape.
 */
export function hasEnumItems(node: RJSFSchema, root: RJSFSchema = node): boolean {
  const field = resolveLocalRef(node, root)
  const items = arrayItems(field)
  return field.type === 'array' && !!items && Array.isArray(resolveLocalRef(items, root).enum)
}
