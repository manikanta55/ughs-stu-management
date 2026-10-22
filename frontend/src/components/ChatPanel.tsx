import { useCallback, useEffect, useRef, useState, type DragEvent, type FormEvent } from 'react'
import { api, classLabel, type SchoolClass, type Upload, type UploadSummary } from '../api/client'
import { UploadCard } from './UploadCard'

type Message =
  | { id: string; role: 'user'; text: string; fileName?: string }
  | { id: string; role: 'assistant'; text: string }
  | { id: string; role: 'upload'; upload: Upload }

interface Props {
  schoolClass: SchoolClass
  onImportFinished: () => void
}

const ACCEPTED = ['.csv', '.xlsx']
const POLL_MS = 1500

let nextId = 0
const newId = () => `m${++nextId}`

function welcome(label: string): Message {
  return {
    id: 'welcome',
    role: 'assistant',
    text:
      `Hi! Attach a .csv or .xlsx roster and I'll import the students into ${label}. ` +
      'Messy files are fine. Add a note with the file if something needs explaining, ' +
      'e.g. "dates are month/day/year".',
  }
}

export function ChatPanel({ schoolClass, onImportFinished }: Props) {
  const classId = schoolClass.id
  const label = classLabel(schoolClass)
  const [messages, setMessages] = useState<Message[]>(() => [welcome(label)])
  const [text, setText] = useState('')
  const [file, setFile] = useState<File | null>(null)
  const [busy, setBusy] = useState(false)
  const [dragging, setDragging] = useState(false)
  const polling = useRef(new Set<number>())
  const mounted = useRef(true)
  const fileInput = useRef<HTMLInputElement>(null)
  const threadEnd = useRef<HTMLDivElement>(null)

  const push = useCallback((m: Message) => setMessages((ms) => [...ms, m]), [])

  const updateUpload = useCallback((u: Partial<Upload> & { id: number }) => {
    setMessages((ms) =>
      ms.map((m) => (m.role === 'upload' && m.upload.id === u.id ? { ...m, upload: { ...m.upload, ...u } } : m)),
    )
  }, [])

  // Poll an import until it finishes; the server commits progress after every agent turn.
  const poll = useCallback(
    (uploadId: number) => {
      if (polling.current.has(uploadId)) return
      polling.current.add(uploadId)
      const tick = async () => {
        if (!mounted.current) return
        try {
          const u = await api.getUpload(uploadId)
          updateUpload(u)
          if (u.status === 'processing') {
            setTimeout(tick, POLL_MS)
            return
          }
          onImportFinished()
        } catch {
          setTimeout(tick, POLL_MS * 2) // transient network error: keep trying
          return
        }
        polling.current.delete(uploadId)
      }
      void tick()
    },
    [onImportFinished, updateUpload],
  )

  useEffect(() => {
    mounted.current = true
    return () => {
      mounted.current = false
    }
  }, [])

  // Rebuild the thread from this class's past imports, so a reload loses nothing.
  // (App keys this panel by class id, so switching class starts a fresh thread.)
  useEffect(() => {
    let cancelled = false
    api
      .listUploads(classId)
      .then((summaries: UploadSummary[]) =>
        Promise.all([...summaries].reverse().map((s) => api.getUpload(s.id))),
      )
      .then((uploads) => {
        if (cancelled) return
        const history = uploads.map((u): Message => ({ id: `upload-${u.id}`, role: 'upload', upload: u }))
        // Past imports go right after the welcome; keep anything sent while they loaded.
        setMessages((ms) => {
          const seen = new Set(ms.map((m) => m.id))
          return [ms[0], ...history.filter((m) => !seen.has(m.id)), ...ms.slice(1)]
        })
        uploads.filter((u) => u.status === 'processing').forEach((u) => poll(u.id))
      })
      .catch((e: Error) => {
        if (!cancelled) push({ id: newId(), role: 'assistant', text: `Could not load past imports: ${e.message}` })
      })
    return () => {
      cancelled = true
    }
  }, [classId, poll, push])

  useEffect(() => {
    threadEnd.current?.scrollIntoView({ behavior: 'smooth', block: 'end' })
  }, [messages])

  function pickFile(f: File | undefined) {
    if (!f) return
    const ext = f.name.slice(f.name.lastIndexOf('.')).toLowerCase()
    if (!ACCEPTED.includes(ext)) {
      push({ id: newId(), role: 'assistant', text: `"${f.name}" isn't a .csv or .xlsx file.` })
      return
    }
    setFile(f)
  }

  async function startImport(uploadId: number, instructions?: string) {
    const started = await api.processUpload(uploadId, instructions)
    updateUpload(started)
    poll(uploadId)
  }

  async function send(e?: FormEvent) {
    e?.preventDefault()
    const note = text.trim()
    if (busy || (!file && !note)) return
    const attached = file
    setText('')
    setFile(null)
    push({ id: newId(), role: 'user', text: note, fileName: attached?.name })

    if (!attached) {
      push({
        id: newId(),
        role: 'assistant',
        text: 'I can only import rosters for now. Attach a .csv or .xlsx file with 📎 (or drop it here), and send your note along with it.',
      })
      return
    }

    setBusy(true)
    try {
      const upload = await api.uploadRoster(classId, attached)
      push({ id: `upload-${upload.id}`, role: 'upload', upload })
      await startImport(upload.id, note || undefined)
    } catch (err) {
      push({ id: newId(), role: 'assistant', text: `⚠️ ${(err as Error).message}` })
    } finally {
      setBusy(false)
    }
  }

  async function retry(uploadId: number) {
    try {
      await startImport(uploadId)
    } catch (err) {
      push({ id: newId(), role: 'assistant', text: `⚠️ ${(err as Error).message}` })
    }
  }

  function onDrop(e: DragEvent) {
    e.preventDefault()
    setDragging(false)
    pickFile(e.dataTransfer.files[0])
  }

  return (
    <section
      className={`panel chat${dragging ? ' dragging' : ''}`}
      onDragOver={(e) => {
        e.preventDefault()
        setDragging(true)
      }}
      onDragLeave={() => setDragging(false)}
      onDrop={onDrop}
    >
      <header className="panel-header">
        <h2>Import assistant</h2>
      </header>

      <div className="thread" aria-live="polite">
        {messages.map((m) =>
          m.role === 'upload' ? (
            <div key={m.id} className="msg assistant">
              <UploadCard upload={m.upload} onRetry={retry} />
            </div>
          ) : (
            <div key={m.id} className={`msg ${m.role}`}>
              <div className="bubble">
                {m.role === 'user' && m.fileName && <div className="attachment">📎 {m.fileName}</div>}
                {m.text && <div>{m.text}</div>}
              </div>
            </div>
          ),
        )}
        <div ref={threadEnd} />
      </div>

      <form className="composer" onSubmit={send}>
        {file && (
          <div className="chip">
            📎 {file.name}
            <button type="button" aria-label="Remove file" onClick={() => setFile(null)}>
              ✕
            </button>
          </div>
        )}
        <div className="composer-row">
          <button
            type="button"
            className="icon-button"
            aria-label="Attach roster file"
            title="Attach .csv or .xlsx"
            onClick={() => fileInput.current?.click()}
          >
            📎
          </button>
          <textarea
            rows={1}
            placeholder={file ? 'Add a note for this file (optional)…' : 'Attach a roster, or drop a file here…'}
            value={text}
            onChange={(e) => setText(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter' && !e.shiftKey) void send(e)
            }}
            maxLength={1000}
          />
          <button type="submit" className="primary" disabled={busy || (!file && !text.trim())}>
            {busy ? 'Uploading…' : 'Send'}
          </button>
        </div>
        <input
          ref={fileInput}
          type="file"
          accept={ACCEPTED.join(',')}
          hidden
          onChange={(e) => {
            pickFile(e.target.files?.[0])
            e.target.value = '' // allow picking the same file again
          }}
        />
      </form>
    </section>
  )
}
