export interface SchoolClass {
  id: number
  grade: string
  section: string
  academic_year: string
  student_count: number
  created_at: string
}

export interface NewClass {
  grade: string
  section: string
  academic_year: string
}

export interface Student {
  id: number
  class_id: number
  upload_id: number | null
  upload_row: number | null
  first_name: string
  last_name: string
  date_of_birth: string | null
  parent_email: string | null
  created_at: string
}

export type UploadStatus = 'parsed' | 'processing' | 'completed' | 'failed'

export interface FlaggedRow {
  row_number: number
  reason: string
  values: Record<string, string>
}

export interface UploadSummary {
  id: number
  class_id: number
  filename: string
  status: UploadStatus
  total_rows: number
  inserted_count: number
  flagged_count: number
  error_message: string | null
  created_at: string
  completed_at: string | null
}

export interface Upload extends UploadSummary {
  agent_stats: { turns: number; tool_calls: number } | null
  columns: string[]
  preview: { row: number; values: Record<string, string> }[]
  flagged_rows: FlaggedRow[]
}

export interface Health {
  status: string
  database: string
}

const API_BASE = import.meta.env.VITE_API_BASE_URL ?? '/api'

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, init)
  if (!res.ok) {
    throw new Error(await errorMessage(res))
  }
  return res.json() as Promise<T>
}

// FastAPI errors are {"detail": "..."} or, for validation errors, {"detail": [{msg}, ...]}.
async function errorMessage(res: Response): Promise<string> {
  try {
    const body = await res.json()
    if (typeof body.detail === 'string') return body.detail
    if (Array.isArray(body.detail)) {
      return body.detail.map((d: { msg: string }) => d.msg).join('; ')
    }
  } catch {
    // not JSON; fall through
  }
  return `${res.status} ${res.statusText}`
}

function postJson<T>(path: string, body: unknown): Promise<T> {
  return request<T>(path, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
}

export const api = {
  health: () => request<Health>('/health'),
  listClasses: () => request<SchoolClass[]>('/classes'),
  createClass: (body: NewClass) => postJson<SchoolClass>('/classes', body),
  listStudents: (classId: number) => request<Student[]>(`/students?class_id=${classId}`),
  listUploads: (classId: number) => request<UploadSummary[]>(`/classes/${classId}/uploads`),
  getUpload: (id: number) => request<Upload>(`/uploads/${id}`),
  uploadRoster: (classId: number, file: File) => {
    const form = new FormData()
    form.append('file', file)
    return request<Upload>(`/classes/${classId}/uploads`, { method: 'POST', body: form })
  },
  processUpload: (id: number, instructions?: string) =>
    postJson<UploadSummary>(`/uploads/${id}/process`, { instructions: instructions ?? null }),
}

export function classLabel(c: SchoolClass): string {
  return `Grade ${c.grade}${c.section ? `-${c.section}` : ''} · ${c.academic_year}`
}
