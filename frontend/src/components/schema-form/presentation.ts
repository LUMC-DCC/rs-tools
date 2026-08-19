import type { RJSFSchema, UiSchema } from '@rjsf/utils'

import { arrayItems, hasEnumItems, resolveLocalRef, subschemas } from '../../lib/schema'

/**
 * Turn schema shapes into the presentation the form should use.
 *
 * The schema is the contract and is never edited; these functions derive a
 * display-only copy of it. Keeping that derivation here means the form
 * component stays about rendering, and adding a presentation rule does not mean
 * touching the editor.
 */

/**
 * Form-wide options that say nothing about any particular field.
 *
 * Nothing here names a schema property, so a schema change needs no edit: the
 * root title is the panel heading, and the form has no submit button because
 * edits save themselves.
 */
export const uiSchema: UiSchema = {
  'ui:title': '',
  'ui:submitButtonOptions': { norender: true },
}

/**
 * Whether a group is only a checklist.
 *
 * RSM wraps a fixed set of choices in `{ entries: [...] }`, sometimes twice, so
 * what reads as one question arrives as a group containing a group. A checklist
 * is already fully visible, so there is nothing to fold away and it is not made
 * collapsible.
 */
function isChecklistGroup(schema: RJSFSchema, root: RJSFSchema, depth = 0): boolean {
  if (depth > 4) return false
  const field = resolveLocalRef(schema, root)
  if (hasEnumItems(field, root)) return true
  const names = Object.keys(subschemas(field))
  return (
    names.length === 1 && isChecklistGroup(subschemas(field)[names[0]], root, depth + 1)
  )
}

/** Whether one array card contains a record with fields of its own. */
function arrayEntriesHaveNestedFields(items: RJSFSchema, root: RJSFSchema): boolean {
  return Object.keys(subschemas(resolveLocalRef(items, root))).length > 0
}

/**
 * Derive the presentation rules the generated form needs.
 *
 * Field titles are left exactly as the schema names them, so nothing here has
 * to be kept in step with the schema by hand. Only two things are decided:
 *
 * - Arrays of fixed choices render as a checklist. Picking from a known set is
 *   a different action from building a list, and an add-and-type list hides
 *   what the options are.
 * - The wrapper titles disappear. RSM holds every list as `{ entries: [...] }`,
 *   so a list would otherwise be headed "authors" followed by "entries", and
 *   each entry labelled "entries-1". The parent title already says what the
 *   list is, and entries are numbered visually.
 */
export function derivePresentationUiSchema(
  schema: RJSFSchema,
  root: RJSFSchema = schema,
  seenRefs: ReadonlySet<string> = new Set(),
): UiSchema {
  // $defs may reference each other; stop if this branch has already been here.
  if (schema.$ref) {
    if (seenRefs.has(schema.$ref)) return {}
    seenRefs = new Set([...seenRefs, schema.$ref])
  }
  const field = resolveLocalRef(schema, root)

  if (hasEnumItems(field, root)) return { 'ui:widget': 'checkboxes' }

  const items = arrayItems(field)
  if (items) {
    return {
      'ui:options': { collapsibleEntries: arrayEntriesHaveNestedFields(items, root) },
      items: {
        'ui:label': false,
        ...derivePresentationUiSchema(items, root, seenRefs),
      },
    }
  }

  const properties = subschemas(field)
  const names = Object.keys(properties)
  const wrapsOneList = names.length === 1 && names[0] === 'entries'

  return Object.fromEntries(
    names.map((name) => {
      const property = properties[name]
      const derived = derivePresentationUiSchema(property, root, seenRefs)
      if (wrapsOneList) return [name, { ...derived, 'ui:label': false }]
      if (isChecklistGroup(property, root)) {
        return [name, { ...derived, 'ui:options': { collapsible: false, checklist: true } }]
      }
      return [name, derived]
    }),
  ) as UiSchema
}

/** Prepare the canonical schema for display without changing the server contract.

 * Choice arrays become unique so a checklist cannot record duplicates.
 * Validation-only conditional branches are removed from this display copy:
 * RJSF otherwise asks Ajv to compile them with dynamic JavaScript, which the
 * production Content Security Policy correctly blocks. The backend continues
 * to validate the unmodified canonical schema on every save.
 */
export function schemaWithChecklistArrays(
  schema: RJSFSchema,
  root: RJSFSchema = schema,
): RJSFSchema {
  const result: RJSFSchema = { ...schema }
  delete result.if
  delete result.then
  delete result.else
  if (hasEnumItems(schema, root)) result.uniqueItems = true
  if (schema.properties) {
    result.properties = Object.fromEntries(
      Object.entries(schema.properties).map(([name, property]) => [
        name,
        schemaWithChecklistArrays(property as RJSFSchema, root),
      ]),
    )
  }
  if (!Array.isArray(schema.items) && schema.items && typeof schema.items === 'object') {
    result.items = schemaWithChecklistArrays(schema.items, root)
  }
  if (schema.$defs) {
    result.$defs = Object.fromEntries(
      Object.entries(schema.$defs).map(([name, definition]) => [
        name,
        schemaWithChecklistArrays(definition as RJSFSchema, root),
      ]),
    )
  }
  return result
}
