# Nginx deployment

Nginx is the only public service. It serves the built React application and
reverse-proxies `/api/` and FastAPI documentation to the private backend
container. PostgreSQL is not published to the host by the production Compose
profile; it is reachable only by the backend on the internal Docker network.

## Start the full stack

From the repository root:

```powershell
docker compose up --build -d
```

Open `http://localhost` for the application. Useful checks:

```powershell
curl http://localhost/nginx-health
curl http://localhost/api/v1/health
```

FastAPI documentation is available at `http://localhost/docs` through Nginx.

For local PostgreSQL integration tests, opt into the development override:

```powershell
docker compose -f docker-compose.yml -f docker-compose.dev.yml up --build -d
```

## Configuration

- `WEB_PORT` changes the host port for Nginx.
- `VITE_API_URL` can override the frontend API base during a special build, but
  the default `/api/v1` is correct for this reverse-proxy deployment.
- TLS should be terminated at Nginx or an upstream load balancer in production.
  Add certificates and redirect HTTP to HTTPS before public deployment.

## Security behavior

- PostgreSQL is internal-only in the Compose stack.
- API responses are marked `no-store`.
- SPA responses include basic browser hardening headers.
- Upload body size is capped at 10 MB.
- Nginx does not replace application authentication or authorization; those still
  need to be implemented before handling real student records.
