import type { ValidationIssue } from '../../types'
import ErrorNotice from './ErrorNotice'

interface ValidationToastProps {
  message: string
  issues?: ValidationIssue[]
  onDismiss: () => void
  onFocusField: (path: string) => void
}

export default function ValidationToast({
  message,
  issues,
  onDismiss,
  onFocusField,
}: ValidationToastProps) {
  const firstPath = issues?.[0]?.path
  return (
    <div className="validation-toast">
      <button type="button" className="toast-close" aria-label="Dismiss validation message" onClick={onDismiss}>
        ×
      </button>
      <ErrorNotice message={message} issues={issues} />
      {firstPath && firstPath !== '$' && (
        <button type="button" className="button toast-field-button" onClick={() => onFocusField(firstPath)}>
          Go to first issue
        </button>
      )}
    </div>
  )
}
