# Frontend component testing

Run:

```powershell
npm test
```

The current tests cover the initial chat workspace, verified-source indicator,
API-aware interface, and Urdu toggle. Add interaction tests for message sending,
navigation, error states, and course/timetable rendering as those screens become
database-backed.

The browser-level chat test is run with:

```powershell
npm run test:e2e
```

It starts Vite and FastAPI automatically. Install a Playwright browser once with
`npx playwright install chromium` if the local browser runtime is absent.
