import { describe, expect, it } from 'vitest'

import { derivePresentationUiSchema, schemaWithChecklistArrays } from './presentation'
import type { SmpSchema } from '../../types'

describe('checklist presentation', () => {
  const schema = {
    type: 'object',
    properties: {
      direct: { type: 'array', items: { type: 'string', enum: ['one', 'two'] } },
      referenced: { type: 'array', items: { $ref: '#/$defs/choice' } },
      contributors: { type: 'array', items: { $ref: '#/$defs/contributor' } },
      status: { type: 'string', enum: ['draft', 'published'] },
    },
    $defs: {
      choice: { type: 'string', enum: ['red', 'blue'] },
      person: {
        type: 'object',
        properties: { roles: { type: 'array', items: { type: 'string', enum: ['author'] } } },
      },
      contributor: {
        allOf: [{ $ref: '#/$defs/person' }],
        properties: { roles: { minItems: 1 } },
        if: { required: ['roles'] },
        then: { required: ['roles'] },
      },
    },
  } as SmpSchema

  it('renders enum arrays as checklists even when the enum is referenced', () => {
    const uiSchema = derivePresentationUiSchema(schema)

    expect(uiSchema.direct).toMatchObject({ 'ui:widget': 'checkboxes' })
    expect(uiSchema.referenced).toMatchObject({ 'ui:widget': 'checkboxes' })
    expect(uiSchema.contributors).toMatchObject({
      items: { roles: { 'ui:widget': 'checkboxes' } },
    })
    expect(uiSchema.status).not.toMatchObject({ 'ui:widget': 'checkboxes' })
  })

  it('makes every enum checklist unique', () => {
    const result = schemaWithChecklistArrays(schema)

    expect(result.properties?.direct).toMatchObject({ uniqueItems: true })
    expect(result.properties?.referenced).toMatchObject({ uniqueItems: true })
  })

  it('removes validation-only conditionals from the display schema', () => {
    const result = schemaWithChecklistArrays(schema)

    expect(result.$defs?.contributor).not.toHaveProperty('if')
    expect(result.$defs?.contributor).not.toHaveProperty('then')
  })
})
