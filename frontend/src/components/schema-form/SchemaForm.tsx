import Form, { type IChangeEvent } from '@rjsf/core'
import { mergeObjects, type UiSchema } from '@rjsf/utils'
import { customizeValidator } from '@rjsf/validator-ajv8'
import Ajv2020 from 'ajv/dist/2020.js'
import { useMemo } from 'react'

import type { SmpData, SmpSchema } from '../../types'
import { derivePresentationUiSchema, schemaWithChecklistArrays, uiSchema } from './presentation'
import { schemaFormTemplates, schemaFormWidgets } from './templates'

// The form neither live-validates nor submits; the server validates the complete
// canonical schema on every save. The display-only schema passed below removes
// validation conditionals so RJSF never asks Ajv to dynamically compile them in
// production, where the Content Security Policy deliberately forbids unsafe-eval.
const validator = customizeValidator({ AjvClass: Ajv2020 })

interface SchemaFormProps {
  data: SmpData
  /** Remounts the form when the visible field set changes. */
  formKey: string
  schema: SmpSchema
  onChange: (data: SmpData) => void
}

/** The generated metadata form. */
export default function SchemaForm({ data, formKey, schema, onChange }: SchemaFormProps) {
  // Both derivations walk the whole schema, so they are memoized on it rather
  // than repeated on every keystroke.
  const presentationSchema = useMemo(() => schemaWithChecklistArrays(schema), [schema])
  const presentationUiSchema = useMemo(
    () => mergeObjects(derivePresentationUiSchema(presentationSchema), uiSchema) as UiSchema,
    [presentationSchema],
  )

  return (
    <div className="schema-form">
      <Form
        key={formKey}
        schema={presentationSchema}
        uiSchema={presentationUiSchema}
        formData={data}
        validator={validator}
        templates={schemaFormTemplates}
        widgets={schemaFormWidgets}
        showErrorList={false}
        onChange={(event: IChangeEvent<SmpData>) => onChange(event.formData || {})}
      />
    </div>
  )
}
