import { env } from '$env/dynamic/private';

/**
 * Base URL of the tagger FastAPI service (see `tagger/`).
 *
 * Server-side only: the browser talks to `/api/tag`, which forwards to this
 * URL. Keeping the call on the server avoids CORS configuration drift and
 * keeps the backend address out of the client bundle.
 *
 * Override with the `TAGGER_URL` environment variable; the default matches a
 * local `uv run uvicorn tagger.main:app --port 8000`.
 */
export const TAGGER_URL = (env.TAGGER_URL || 'http://localhost:8000').replace(/\/+$/, '');
