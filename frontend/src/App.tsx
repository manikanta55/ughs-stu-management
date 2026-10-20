import { useEffect, useState } from 'react'
import { api, type Health, type Student } from './api/client'

function App() {
  const [health, setHealth] = useState<Health | null>(null)
  const [students, setStudents] = useState<Student[]>([])
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    Promise.all([api.health(), api.listStudents()])
      .then(([h, s]) => {
        setHealth(h)
        setStudents(s)
      })
      .catch((e: Error) => setError(e.message))
  }, [])

  return (
    <main className="container">
      <header>
        <h1>UGHS Student Management</h1>
        <p className="status">
          API:{' '}
          {error ? (
            <span className="bad">unreachable ({error})</span>
          ) : health ? (
            <span className="ok">
              {health.status} · database {health.database}
            </span>
          ) : (
            'checking…'
          )}
        </p>
      </header>

      <section>
        <h2>Students ({students.length})</h2>
        <table>
          <thead>
            <tr>
              <th>ID</th>
              <th>First name</th>
              <th>Last name</th>
              <th>Date of birth</th>
              <th>Parent email</th>
            </tr>
          </thead>
          <tbody>
            {students.length === 0 ? (
              <tr>
                <td colSpan={5} className="empty">
                  No students yet — roster upload comes next.
                </td>
              </tr>
            ) : (
              students.map((s) => (
                <tr key={s.id}>
                  <td>{s.id}</td>
                  <td>{s.first_name}</td>
                  <td>{s.last_name}</td>
                  <td>{s.date_of_birth ?? '—'}</td>
                  <td>{s.parent_email ?? '—'}</td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </section>
    </main>
  )
}

export default App
