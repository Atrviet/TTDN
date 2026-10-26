# AI StudyMate Frontend

React/Vite client for the existing AI StudyMate REST API. The interface is in Vietnamese and includes authentication, documents, grounded chat, Study Agent, quizzes, analytics, and a read-only profile.

## Local setup

Requirements: Node.js 18+ and the backend running at `http://127.0.0.1:8000`.

```bash
cp .env.example .env
npm install
npm run dev
```

Open <http://localhost:5173>. Configure a different API origin with:

```dotenv
VITE_API_BASE_URL=http://127.0.0.1:8000/api/v1
```

The backend `CORS_ORIGINS` must contain the frontend origin. No Gemini credential is used or exposed by this browser application.

## Checks

```bash
npm test
npm run build
npm run preview
```

## Authentication and security

- The access token is kept only in JavaScript memory.
- The refresh token is kept in `sessionStorage`, is cleared when the tab session ends, and is used by a single-flight Axios interceptor after a `401` response.
- A failed refresh clears the session and sends the user to `/login`.
- Protected pages require an authenticated profile from `/users/me`.

This is safer than long-lived `localStorage`, but `sessionStorage` remains readable by JavaScript and can be stolen if an XSS vulnerability exists. The current backend returns refresh tokens in JSON and does not provide a revocable `HttpOnly`, `Secure`, `SameSite` cookie flow. For production, prefer rotating refresh tokens in such cookies, server-side revocation/reuse detection, and a strict Content Security Policy.

## Backend integration

The API client follows the OpenAPI document exposed by the current backend. Login is sent as OAuth2 form data; registration and refresh use JSON. Uploads are multipart requests with progress reporting. Correct quiz answers are not requested or displayed until the result endpoint is available after submission.

The profile page is intentionally read-only because the current backend exposes `GET /users/me` but no profile-update endpoint.
