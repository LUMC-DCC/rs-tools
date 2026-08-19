import { getDefaultRegistry } from '@rjsf/core'
import { getUiOptions } from '@rjsf/utils'
import type {
  ArrayFieldItemTemplateProps,
  ArrayFieldTemplateProps,
  IconButtonProps,
  ObjectFieldTemplateProps,
  RegistryWidgetsType,
  TemplatesType,
  UiSchema,
  WidgetProps,
} from '@rjsf/utils'
import { ArrowDown, ArrowUp, Copy, Plus, Trash2 } from 'lucide-react'
import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useRef,
  useState,
  type ReactElement,
  type ReactNode,
} from 'react'

import { FieldDepthProvider, useFieldDepth } from './fieldDepth'

const defaults = getDefaultRegistry().templates

interface ArrayCollapseState {
  collapsed: boolean
  setCollapsed: (collapsed: boolean) => void
}

const ArrayCollapseContext = createContext<ArrayCollapseState | null>(null)

interface ActionButtonProps extends IconButtonProps {
  label: string
  icon: ReactElement
  variant?: 'default' | 'danger'
}

function ActionButton({
  label,
  icon,
  variant = 'default',
  registry: _registry,
  uiSchema: _uiSchema,
  iconType: _iconType,
  className = '',
  title,
  ...buttonProps
}: ActionButtonProps) {
  return (
    <button
      {...buttonProps}
      type="button"
      className={`icon-button ${variant === 'danger' ? 'icon-button-danger' : ''} ${className}`}
      aria-label={title || label}
      title={title || label}
    >
      {icon}
    </button>
  )
}

/** Adding an entry is the one control in a list whose meaning is not obvious
 *  from what sits beside it, so it is labelled rather than an icon alone. */
function AddEntryButton({
  registry: _registry,
  uiSchema: _uiSchema,
  iconType: _iconType,
  className = '',
  ...buttonProps
}: IconButtonProps) {
  return (
    <button {...buttonProps} type="button" className={`add-entry-button ${className}`}>
      <Plus size={12} aria-hidden="true" />
      Add entry
    </button>
  )
}

const buttonTemplates: Partial<TemplatesType['ButtonTemplates']> = {
  AddButton: AddEntryButton,
  RemoveButton: (props) => (
    <ActionButton {...props} label="Delete entry" icon={<Trash2 size={14} />} variant="danger" />
  ),
  MoveUpButton: (props) => (
    <ActionButton {...props} label="Move entry up" icon={<ArrowUp size={14} />} />
  ),
  MoveDownButton: (props) => (
    <ActionButton {...props} label="Move entry down" icon={<ArrowDown size={14} />} />
  ),
  CopyButton: (props) => (
    <ActionButton {...props} label="Duplicate entry" icon={<Copy size={14} />} />
  ),
  ClearButton: (props) => (
    <ActionButton {...props} label="Clear value" icon={<Trash2 size={14} />} />
  ),
}

/**
 * A text field that grows to fit what is in it.
 *
 * The schema cannot say which strings hold a sentence and which hold an essay —
 * `project_name` and `project_long_description` are both bare
 * `{"type": "string"}`. Listing the long ones by name would be a mapping to
 * maintain against a schema that changes, so instead every plain string starts
 * one line tall and grows as it is typed into. Fields with a format or a fixed
 * set of choices keep their own widgets.
 */
function GrowingTextWidget({
  id,
  value,
  disabled,
  readonly,
  autofocus,
  placeholder,
  options,
  onChange,
  onBlur,
  onFocus,
}: WidgetProps) {
  const field = useRef<HTMLTextAreaElement | null>(null)

  const fit = useCallback(() => {
    const element = field.current
    if (!element) return
    element.style.height = 'auto'
    element.style.height = `${element.scrollHeight}px`
  }, [])

  // Re-fit on external changes too, such as switching back from the raw editor.
  useEffect(fit, [fit, value])

  return (
    <textarea
      id={id}
      ref={field}
      className="form-control growing-text"
      rows={1}
      value={(value as string | undefined) ?? ''}
      disabled={disabled}
      readOnly={readonly}
      autoFocus={autofocus}
      placeholder={placeholder}
      onChange={(event) => {
        fit()
        onChange(event.target.value === '' ? options.emptyValue : event.target.value)
      }}
      onBlur={(event) => onBlur(id, event.target.value)}
      onFocus={(event) => onFocus(id, event.target.value)}
    />
  )
}

/** Boolean labels lead their checkboxes, matching the label-first reading
 * order of every other metadata field. */
function BooleanWidget({
  id,
  value,
  disabled,
  readonly,
  autofocus,
  label,
  hideLabel,
  schema,
  onChange,
  onBlur,
  onFocus,
}: WidgetProps) {
  const description = typeof schema.description === 'string' ? schema.description : undefined

  return (
    <div className="boolean-field-control">
      <label className="boolean-field-label" htmlFor={id}>
        {!hideLabel && <span>{label}</span>}
        <input
          type="checkbox"
          id={id}
          checked={Boolean(value)}
          disabled={disabled || readonly}
          autoFocus={autofocus}
          onChange={(event) => onChange(event.target.checked)}
          onBlur={(event) => onBlur(id, event.target.checked)}
          onFocus={(event) => onFocus(id, event.target.checked)}
        />
      </label>
      {!hideLabel && description && <p className="field-description">{description}</p>}
    </div>
  )
}

export const schemaFormWidgets: RegistryWidgetsType = {
  TextWidget: GrowingTextWidget,
  CheckboxWidget: BooleanWidget,
}

interface FieldGroupProps {
  depth: number
  title?: string
  required?: boolean
  uiSchema?: UiSchema
  children: ReactNode
}

/** A named schema group. Only array entries use disclosures: a field's title
 * and explanation should stay visible while its values are being edited. */
function FieldGroup({ depth, title, required, uiSchema, children }: FieldGroupProps) {
  const options = getUiOptions(uiSchema)
  // A group whose label is suppressed has nothing to fold behind: RSM wraps
  // every list in `{ entries: [...] }`, and that wrapper is an artefact of the
  // schema rather than something a reader should have to open.
  const named = title && options.label !== false
  const className = `field-group ${!named ? 'unnamed-field-group' : ''} ${
    options.checklist === true ? 'checklist-group' : ''
  }`
  // The root is the form itself: there is nothing to label above it.
  if (depth === 0 || !named) {
    return (
      <div className={className} data-depth={depth}>{children}</div>
    )
  }

  const label = (
    <>
      {title}
      {required && <span className="required">*</span>}
    </>
  )

  return (
    <div className={className} data-depth={depth}>
      <p className="field-group-label">{label}</p>
      {children}
    </div>
  )
}

function GroupedObjectField(props: ObjectFieldTemplateProps) {
  const depth = useFieldDepth()
  const { ObjectFieldTemplate } = defaults
  return (
    <FieldGroup
      depth={depth}
      title={props.title}
      required={props.required}
      uiSchema={props.uiSchema}
    >
      <FieldDepthProvider depth={depth + 1}>
        <ObjectFieldTemplate {...props} title="" />
      </FieldDepthProvider>
    </FieldGroup>
  )
}

function GroupedArrayField(props: ArrayFieldTemplateProps) {
  const depth = useFieldDepth()
  const { ArrayFieldTemplate } = defaults
  const collapsibleEntries = getUiOptions(props.uiSchema).collapsibleEntries === true
  const [collapsed, setCollapsed] = useState(false)

  return (
    <FieldGroup
      depth={depth}
      title={props.title}
      required={props.required}
      uiSchema={props.uiSchema}
    >
      <FieldDepthProvider depth={depth + 1}>
        <ArrayCollapseContext.Provider
          value={collapsibleEntries ? { collapsed, setCollapsed } : null}
        >
          <ArrayFieldTemplate {...props} title="" />
        </ArrayCollapseContext.Provider>
      </FieldDepthProvider>
    </FieldGroup>
  )
}

/**
 * Lay an array entry out as a block with its controls underneath.
 *
 * The stock template puts the move and delete buttons in a column beside the
 * entry, which squeezes the entry itself and reads as if the buttons belong to
 * the field next to them. Replacing it is what makes that possible: the stock
 * version sets its flex layout with inline styles, which no stylesheet can
 * override without `!important` on every rule.
 */
function ArrayEntry({
  children,
  className,
  buttonsProps,
  hasToolbar,
  index,
  parentUiSchema,
  registry,
  uiSchema,
}: ArrayFieldItemTemplateProps) {
  const { ArrayFieldItemButtonsTemplate } = registry.templates
  const collapseState = useContext(ArrayCollapseContext)
  const collapsible = getUiOptions(parentUiSchema).collapsibleEntries === true && collapseState
  const actions = hasToolbar && (
    <div className="rjsf-array-item-actions" onClick={(event) => event.stopPropagation()}>
      <div className="btn-group">
        <ArrayFieldItemButtonsTemplate {...buttonsProps} uiSchema={uiSchema} />
      </div>
    </div>
  )
  return (
    <div className={className}>
      {collapsible ? (
        <details
          className="array-entry-details"
          open={!collapseState.collapsed}
          onToggle={(event) => collapseState.setCollapsed(!event.currentTarget.open)}
        >
          <summary className="array-entry-summary">
            <span>Entry {index + 1}</span>
            {actions}
          </summary>
          <div className="rjsf-array-item-content">{children}</div>
        </details>
      ) : (
        <>
          <div className="array-entry-header">
            <span>Entry {index + 1}</span>
            {actions}
          </div>
          <div className="rjsf-array-item-content">{children}</div>
        </>
      )}
    </div>
  )
}

export const schemaFormTemplates: Partial<TemplatesType> = {
  ButtonTemplates: buttonTemplates as TemplatesType['ButtonTemplates'],
  ObjectFieldTemplate: GroupedObjectField,
  ArrayFieldTemplate: GroupedArrayField,
  ArrayFieldItemTemplate: ArrayEntry,
}
