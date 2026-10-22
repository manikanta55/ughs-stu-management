# Backlog: Enhancements & Open Decisions

The current build is a **trial working solution**. The items below are deliberately deferred until we have real roster data and confirmed requirements. Revisit them before finalizing the schema and going to production.

## Data model (finalize with real roster data)

- [ ] **Enrollment history.** Right now a student has a single `class_id`, so promoting a student (Grade 5 → 6) overwrites the old class. If past years matter, add an `enrollments` table (`student_id`, `class_id`, one row per academic year) and drop `students.class_id`. This is easiest to change while the DB is empty or small.
- [ ] **Duplicate students on re-upload.** Uploading the same roster twice inserts duplicates. Options:
  - Match on a school-issued **admission / roll number** (preferred, if the rosters have one), with a unique constraint.
  - Otherwise match on `(class_id, first_name, last_name, date_of_birth)` during upload. Note that Postgres treats NULLs as distinct, so a missing DOB weakens this.
- [ ] **Student fields.** Confirm the real column set from actual rosters (e.g. gender, guardian name/phone, address, admission number) and whether `parent_email` / `date_of_birth` should be required.
- [ ] **Single-name students.** `last_name` is required, so a student listed only as "Meena" must be flagged (or the agent invents a surname, which we don't want). Common in Indian rosters — consider making `last_name` optional or adding a `full_name` field.
- [ ] **Date-of-birth sanity range.** Currently any date from 1950-01-01 up to yesterday is accepted. Tighten to a realistic school-age range per grade once confirmed.
- [ ] **Class fields.** Confirm grade naming (numeric vs. LKG/UKG), whether sections are always present, and the academic-year format (`2026-27`).

## Roster file parsing

- [ ] **Only the first sheet of an `.xlsx` is read.** Decide whether multi-sheet workbooks (e.g. one sheet per section) should be supported.
- [ ] **Old `.xls` files are rejected.** Supporting them needs the `xlrd` package; or ask teachers to re-save as `.xlsx`.
- [ ] **Header detection is a heuristic** (first row filling at least half the columns). Revisit once we see real files; the agent could choose the header row instead.
- [ ] **Unquoted commas in CSV cells** (e.g. `KUMAR, Ravi`) shift the rest of that row. The parser keeps the row as written; the agent should repair or flag it. Check how often this happens in real exports.
- [ ] **Retention of parsed rows.** `roster_uploads.rows` keeps a full copy of every uploaded file's data (student PII). Decide how long to keep it, e.g. clear it after processing or after N days.

## Deployment / production

- [ ] Choose a managed Postgres provider (Neon/Supabase for staging; RDS/Cloud SQL/Azure/Render/Railway for production).
- [ ] Set `DATABASE_URL` through the host's secrets, with `?sslmode=require`, a strong password, and network access restricted to the backend.
- [ ] Run `alembic upgrade head` as part of every deploy.
- [ ] **Student PII:** choose the provider region to match the school's data rules; enable automated backups.

## Tooling

- [ ] Upgrade Node 20 (end-of-life since April 2026) to Node 22+ LTS. This should also remove the need for the `npx npm@11` workaround in `make install` (npm 10.8.2 crashes on this dependency tree).

## Agentic uploader

- [x] Pick the LLM provider and get an API key (Claude, `claude-opus-5-5`).
- [ ] **Background jobs run inside the API process** (FastAPI `BackgroundTasks`). If the server restarts mid-import, the upload stays `processing` forever. For production, use a job queue (e.g. Arq/Celery/RQ) or at least reset stale `processing` uploads on startup.
- [ ] **Date order assumption.** Ambiguous numeric dates (02/04/2016) are read day-first unless other rows in the column show otherwise. Confirm with the school; make it a per-school setting if needed.
- [ ] **Invalid optional values flag the whole row** (e.g. a good name with an incomplete email). Alternative: insert the student and attach a warning for the teacher. Needs a "warnings" concept in the data model.
- [ ] **Failed runs keep partial progress** (rows inserted before the failure stay). Re-running the import continues with the remaining rows only. Decide whether teachers would rather have all-or-nothing.
- [ ] **Cost tracking.** `roster_uploads.agent_stats` records turns, tool calls and tokens per run (the 6-row sample costs roughly $0.05). Add a dashboard or monthly budget alert if usage grows.
- [ ] **Free-text chat.** The chat box currently only imports files (text sent with a file becomes notes for the agent; text alone gets a help reply). A real conversational assistant — "who is missing a DOB in 5-A?", "fix row 7's surname to Iyer" — needs a chat endpoint with read/update tools.
- [ ] **Large files.** All rows go into a single conversation. Very large files (hundreds of rows) may need to be split into chunks of e.g. 100 rows per agent run.
