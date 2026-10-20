export interface Student {
  id: number
  first_name: string
  last_name: string
  date_of_birth: string | null
  parent_email: string | null
  created_at: string
}

export interface Health {
  status: string
  database: string
}

const API_BASE = import.meta.env.VITE_API_BASE_URL ?? '/api'

async function get<T>(path: string): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`)
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`)
  return res.json() as Promise<T>
}

export const api = {
  health: () => get<Health>('/health'),
  listStudents: () => get<Student[]>('/students'),
}
