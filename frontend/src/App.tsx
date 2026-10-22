import { useCallback, useEffect, useState } from 'react'
import { api, classLabel, type SchoolClass } from './api/client'
import { ChatPanel } from './components/ChatPanel'
import { ClassPicker } from './components/ClassPicker'
import { RosterPanel } from './components/RosterPanel'

const SELECTED_KEY = 'ughs.selectedClassId'

function storedClassId(): number | null {
  try {
    const v = localStorage.getItem(SELECTED_KEY)
    return v ? Number(v) : null
  } catch {
    return null
  }
}

function App() {
  const [classes, setClasses] = useState<SchoolClass[] | null>(null)
  const [selectedId, setSelectedId] = useState<number | null>(storedClassId)
  const [apiError, setApiError] = useState<string | null>(null)
  const [rosterVersion, setRosterVersion] = useState(0)

  const loadClasses = useCallback(
    () =>
      api
        .listClasses()
        .then((list) => {
          setClasses(list)
          setApiError(null)
          setSelectedId((id) =>
            id !== null && list.some((c) => c.id === id) ? id : (list[0]?.id ?? null),
          )
        })
        .catch((e: Error) => setApiError(e.message)),
    [],
  )

  useEffect(() => {
    void loadClasses()
  }, [loadClasses])

  useEffect(() => {
    try {
      if (selectedId !== null) localStorage.setItem(SELECTED_KEY, String(selectedId))
    } catch {
      // storage unavailable (private mode); selection just isn't remembered
    }
  }, [selectedId])

  // After an import: refresh the roster table and the student counts in the picker.
  const onImportFinished = useCallback(() => {
    setRosterVersion((v) => v + 1)
    void loadClasses()
  }, [loadClasses])

  const selected = classes?.find((c) => c.id === selectedId) ?? null

  return (
    <div className="app">
      <header className="topbar">
        <h1>UGHS Student Management</h1>
        {classes && (
          <ClassPicker
            classes={classes}
            selectedId={selectedId}
            onSelect={setSelectedId}
            onCreated={(c) => {
              setClasses((cs) => [...(cs ?? []), c])
              setSelectedId(c.id)
            }}
          />
        )}
      </header>

      {apiError && (
        <p className="banner-error">
          Can't reach the API ({apiError}). Is the backend running? <code>make backend</code>
        </p>
      )}

      {selected ? (
        <main className="layout">
          <ChatPanel key={selected.id} schoolClass={selected} onImportFinished={onImportFinished} />
          <RosterPanel classId={selected.id} title={classLabel(selected)} refreshKey={rosterVersion} />
        </main>
      ) : (
        classes && (
          <main className="empty-state">
            <p>Create a class above to start importing rosters.</p>
          </main>
        )
      )}
    </div>
  )
}

export default App
