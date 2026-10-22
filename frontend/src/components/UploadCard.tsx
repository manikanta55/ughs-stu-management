import type { Upload } from '../api/client'

interface Props {
  upload: Upload
  onRetry: (id: number) => void
}

const STATUS_LABEL: Record<Upload['status'], string> = {
  parsed: 'Not imported',
  processing: 'Importing…',
  completed: 'Done',
  failed: 'Failed',
}

export function UploadCard({ upload, onRetry }: Props) {
  const handled = upload.inserted_count + upload.flagged_count
  const percent = upload.total_rows ? Math.round((handled / upload.total_rows) * 100) : 0

  return (
    <div className="upload-card">
      <div className="upload-card-head">
        <span className="file-name">📄 {upload.filename}</span>
        <span className={`badge badge-${upload.status}`}>{STATUS_LABEL[upload.status]}</span>
      </div>

      <p>
        Read <strong>{upload.total_rows}</strong> rows with columns{' '}
        <span className="muted">{upload.columns.join(', ')}</span>.
      </p>

      {upload.preview.length > 0 && (
        <details>
          <summary>Preview of the file</summary>
          <div className="table-scroll">
            <table className="compact">
              <thead>
                <tr>
                  <th>Row</th>
                  {upload.columns.map((c) => (
                    <th key={c}>{c}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {upload.preview.map((r) => (
                  <tr key={r.row}>
                    <td>{r.row}</td>
                    {upload.columns.map((c) => (
                      <td key={c}>{r.values[c]}</td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </details>
      )}

      {upload.status === 'parsed' && (
        <p>
          <button type="button" className="primary" onClick={() => onRetry(upload.id)}>
            Start import
          </button>
        </p>
      )}

      {upload.status === 'processing' && (
        <div className="progress" aria-label="Import progress">
          <div className="progress-bar" style={{ width: `${Math.max(percent, 4)}%` }} />
          <span className="muted">
            Claude is reading and cleaning the rows… {handled}/{upload.total_rows} handled
          </span>
        </div>
      )}

      {upload.status === 'completed' && (
        <p>
          ✅ Imported <strong>{upload.inserted_count}</strong> of {upload.total_rows} students.
          {upload.flagged_count === 0
            ? ' Every row was imported.'
            : ` ${upload.flagged_count} ${upload.flagged_count === 1 ? 'row needs' : 'rows need'} your attention:`}
        </p>
      )}

      {upload.status === 'failed' && (
        <div className="failed">
          <p>⚠️ {upload.error_message ?? 'The import failed.'}</p>
          <p className="muted">
            {upload.inserted_count} imported and {upload.flagged_count} flagged so far. Retrying
            continues with the remaining rows.
          </p>
          <button type="button" className="primary" onClick={() => onRetry(upload.id)}>
            Retry import
          </button>
        </div>
      )}

      {upload.flagged_rows.length > 0 && (
        <div className="table-scroll">
          <table className="compact flagged">
            <thead>
              <tr>
                <th>Row</th>
                <th>Problem</th>
              </tr>
            </thead>
            <tbody>
              {upload.flagged_rows.map((f) => (
                <tr key={f.row_number}>
                  <td>{f.row_number}</td>
                  <td>{f.reason}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {upload.agent_stats && upload.status !== 'processing' && (
        <p className="muted small">
          {upload.agent_stats.turns} steps · {upload.agent_stats.tool_calls} tool calls
        </p>
      )}
    </div>
  )
}
