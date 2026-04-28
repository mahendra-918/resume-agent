# Resume Agent — Phase 2 Task Breakdown

## Phase 2A: Smart De-Duplication ✅ COMPLETE
- `[x]` Add a `is_already_applied(job_url: str)` query function in `db/repository.py`
- `[x]` Update `process_next_job_node` in `pipeline.py` to call the above and skip already-applied jobs
- `[x]` Add `None` guards in `tailor_resume_node` and `apply_job_node` to short-circuit duplicates
- `[x]` Log a clear `[Pipeline] Skipping duplicate: {job.title}` message when a job is skipped

---

## Phase 2B: Resume File Upload ✅ COMPLETE

### Backend
- `[x]` Create a `POST /upload` endpoint in `api.py` that accepts a `multipart/form-data` file
- `[x]` Validate the uploaded file extension (`.pdf`, `.docx` only)
- `[x]` Save the uploaded file to `output/resumes/{filename}` on the server
- `[x]` Return the saved file path in the response so the frontend can pass it to `POST /run`

### Frontend
- `[x]` Build a drag-and-drop `FileDropZone` component in `RunPage.jsx`
- `[x]` Wire the file picker to call `POST /upload` on file selection
- `[x]` Store the returned file path in React state and automatically populate `resume_path`
- `[x]` Show a success indicator (✅ filename + "click to replace") after the upload completes

---

## Phase 2C: Application History Dashboard ✅ COMPLETE

### Backend
- `[x]` Verify `GET /status` returns all required fields (it does — already done)
- `[x]` Add `GET /status/summary` endpoint returning counts (Handled efficiently on frontend instead)

### Frontend
- `[x]` Create a new `HistoryPage.jsx` component
- `[x]` Add a "History" link to the navigation bar in `App.jsx` and `Navbar.jsx`
- `[x]` Build a sortable data table displaying all applications from `GET /status`
- `[x]` Add color-coded status badges (green = Applied, orange = Skipped, red = Failed)
- `[x]` Add a search/filter bar to filter by platform or job title
- `[x]` Add a "Clear All" button that calls `DELETE /applications`
- `[x]` Add a summary card at the top showing total counts per status

---

## Phase 2D: Tailored Resume Upload via Playwright

### Backend
- `[ ]` Confirm `tailor_resume_node` saves tailored resume file to disk with a predictable path
- `[ ]` Pass tailored resume file path through `AgentState` to the `apply_job_node`

### Naukri Platform
- `[ ]` Locate the resume upload `<input type="file">` button in the Naukri apply form
- `[ ]` Use `page.set_input_files(selector, file_path)` to attach the tailored PDF
- `[ ]` Add a wait + verification step to confirm the upload was accepted

### LinkedIn Platform
- `[ ]` Same file upload flow as Naukri using `page.set_input_files()`
- `[ ]` Handle cases where LinkedIn uses "Easy Apply" modal vs external job site

### Testing
- `[ ]` Run end-to-end test and verify the tailored resume file appears in the submission
