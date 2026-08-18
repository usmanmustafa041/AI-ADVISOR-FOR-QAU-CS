# QAU CS Academic Advisor — frontend

React/Vite student portal UI for Step 9. It includes the chat workspace,
academic overview, verified course catalogue, and timetable status view.

## Run

```powershell
npm install
npm run dev
```

Set `VITE_API_URL` when the FastAPI service is not running at
`http://localhost:8000/api/v1`.

The chat UI calls the authenticated `/chat` workflow and clearly reports API
errors. It never invents timetable records: unavailable official records are
shown as unavailable.

The completed portal includes student registration/login, bilingual chat, saved
history, course and policy search, timetable lookup, and a role-based admin
dashboard covering all management use cases. Run the full stack with
`docker compose up -d --build` from the repository root and open
`http://localhost`.

The development database includes a visibly labeled synthetic Fall 2026 dataset
for demonstrating timetable, exam, deadline, fee, prerequisite, and FYP flows.
It is not official QAU data and must not be used for academic decisions.
