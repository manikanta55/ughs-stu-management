import { useEffect, useState } from 'react'
import { api, type Student } from '../api/client'

interface Props {
  classId: number
  title: string
  refreshKey: number
}

export function RosterPanel({ classId, title, refreshKey }: Props) {
  const [students, setStudents] = useState<Student[] | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false
    api
      .listStudents(classId)
      .then((s) => {
        if (!cancelled) {
          setStudents(s)
          setError(null)
        }
      })
      .catch((e: Error) => !cancelled && setError(e.message))
    return () => {
      cancelled = true
    }
  }, [classId, refreshKey])

  return (
    <section className="panel roster">
      <header className="panel-header">
        <h2>{title}</h2>
        <span className="muted">{students ? `${students.length} students` : ''}</span>
      </header>
      {error && <p className="form-error">Could not load students: {error}</p>}
      <div className="table-scroll">
        <table>
          <thead>
            <tr>
              <th>Name</th>
              <th>Date of birth</th>
              <th>Parent email</th>
              <th>Source</th>
            </tr>
          </thead>
          <tbody>
            {students === null ? (
              <tr>
                <td colSpan={4} className="empty">
                  Loading…
                </td>
              </tr>
            ) : students.length === 0 ? (
              <tr>
                <td colSpan={4} className="empty">
                  No students yet. Upload a roster in the chat to add some.
                </td>
              </tr>
            ) : (
              students.map((s) => (
                <tr key={s.id}>
                  <td>
                    {s.first_name} {s.last_name}
                  </td>
                  <td>{s.date_of_birth ?? '—'}</td>
                  <td className="break">{s.parent_email ?? '—'}</td>
                  <td className="muted">
                    {s.upload_id ? `Upload #${s.upload_id}, row ${s.upload_row}` : 'Manual'}
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </section>
  )
}
