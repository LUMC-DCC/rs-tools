import type { ValidationIssue } from '../../types'

interface ErrorNoticeProps {
  title?: string
  message: string
  issues?: ValidationIssue[]
}

export default function ErrorNotice({
  title = 'Something needs attention',
  message,
  issues,
}: ErrorNoticeProps) {
  return (
    <div className="notice notice-error" role="alert">
      <div className="notice-icon" aria-hidden="true">
        !
      </div>
      <div>
        <strong>{title}</strong>
        <p>{message}</p>
        {issues && issues.length > 0 && (
          <ul>
            {issues.slice(0, 8).map((issue, index) => (
              <li key={`${issue.path}-${index}`}>
                <code>{issue.path}</code> {issue.message}
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  )
}

