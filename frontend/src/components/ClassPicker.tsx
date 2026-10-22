import { useState, type FormEvent } from 'react'
import { api, classLabel, type SchoolClass } from '../api/client'

interface Props {
  classes: SchoolClass[]
  selectedId: number | null
  onSelect: (id: number) => void
  onCreated: (c: SchoolClass) => void
}

// The school year starts in June: before that, we are still in last year's session.
function currentAcademicYear(): string {
  const now = new Date()
  const start = now.getMonth() >= 5 ? now.getFullYear() : now.getFullYear() - 1
  return `${start}-${String((start + 1) % 100).padStart(2, '0')}`
}

export function ClassPicker({ classes, selectedId, onSelect, onCreated }: Props) {
  const [creating, setCreating] = useState(classes.length === 0)
  const [grade, setGrade] = useState('')
  const [section, setSection] = useState('')
  const [year, setYear] = useState(currentAcademicYear)
  const [error, setError] = useState<string | null>(null)
  const [saving, setSaving] = useState(false)

  async function create(e: FormEvent) {
    e.preventDefault()
    setSaving(true)
    setError(null)
    try {
      const created = await api.createClass({
        grade: grade.trim(),
        section: section.trim(),
        academic_year: year.trim(),
      })
      onCreated(created)
      setCreating(false)
      setGrade('')
      setSection('')
    } catch (err) {
      setError((err as Error).message)
    } finally {
      setSaving(false)
    }
  }

  if (creating) {
    return (
      <form className="class-form" onSubmit={create}>
        <input
          aria-label="Grade"
          placeholder="Grade (e.g. 5)"
          value={grade}
          onChange={(e) => setGrade(e.target.value)}
          required
        />
        <input
          aria-label="Section"
          placeholder="Section (e.g. A)"
          value={section}
          onChange={(e) => setSection(e.target.value)}
        />
        <input
          aria-label="Academic year"
          placeholder="2026-27"
          pattern="\d{4}-\d{2}"
          title="Format: 2026-27"
          value={year}
          onChange={(e) => setYear(e.target.value)}
          required
        />
        <button type="submit" className="primary" disabled={saving}>
          {saving ? 'Creating…' : 'Create class'}
        </button>
        {classes.length > 0 && (
          <button type="button" onClick={() => setCreating(false)}>
            Cancel
          </button>
        )}
        {error && <span className="form-error">{error}</span>}
      </form>
    )
  }

  return (
    <div className="class-picker">
      <select
        aria-label="Class"
        value={selectedId ?? ''}
        onChange={(e) => onSelect(Number(e.target.value))}
      >
        {classes.map((c) => (
          <option key={c.id} value={c.id}>
            {classLabel(c)} ({c.student_count} students)
          </option>
        ))}
      </select>
      <button type="button" onClick={() => setCreating(true)}>
        + New class
      </button>
    </div>
  )
}
