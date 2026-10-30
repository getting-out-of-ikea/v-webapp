# tagger

Automatic image tagging service backed by Google Cloud Vision.

## Setup

    cd tagger
    uv sync
    cp ../.env.example .env    # then edit it

`uv` installs the Python version pinned in `.python-version` and the exact
dependency set recorded in `uv.lock`. Do not `pip install` into the project
environment by hand; add dependencies with `uv add` (runtime) or
`uv add --dev` (development) so the lock file stays in sync.

Run every command **from `tagger/`**: the service reads `.env` and resolves the
credential path against the current working directory.

## Credentials

The service authenticates through Application Default Credentials:

- locally, download a service-account key with `vision.images.annotate` on the
  project and point `GOOGLE_APPLICATION_CREDENTIALS` at it — `.env.example`
  suggests `ignore/service-account.json`, which must stay git-ignored;
- deployed, the service account is attached to the runtime (Workload Identity
  or Cloud Run), so the variable stays empty and no key ships with the image.

`.env` values are not exported to the process environment, so the application
copies `GOOGLE_APPLICATION_CREDENTIALS` into `os.environ` at startup, where
google-auth looks for it. An already exported variable takes precedence. The
path is converted to absolute, so a relative entry in `.env` always means the
same file regardless of where the process was started.

`gcloud auth application-default login` is a valid alternative to a key file
for local development.

## Run

    uv run uvicorn tagger.main:app --host 0.0.0.0 --port 8000 --reload
    uv run tagger                          # no auto-reload, honours PORT

## Check

    curl -s localhost:8000/health

`/health` answers `200` with `status: "ok"` when the credentials work, and
`status: "degraded"` plus a short `error` category when they do not. The check
is cached for `HEALTH_CACHE_TTL_S` seconds, so probing does not cost an OAuth
round trip per request. The response never contains credential details; the
underlying exception goes to the log.

The categories, in the order the probe reaches them:

| `error`                                    | meaning                                                     |
|--------------------------------------------|-------------------------------------------------------------|
| `credentials file not found`               | `GOOGLE_APPLICATION_CREDENTIALS` points at nothing          |
| `credentials path is not a file`           | it points at a directory                                    |
| `credentials file is not valid JSON`       | truncated download, or not JSON at all                      |
| `credentials file is not a Google key`     | e.g. an OAuth client secret instead of a service account    |
| `application default credentials not found`| no key configured and no ADC on the machine                 |
| `credentials unusable`                     | google-auth rejected the source for another reason          |
| `token endpoint unreachable`               | network or DNS problem, not a permissions one               |
| `token refresh rejected`                   | Google refused: revoked key, missing scope, API disabled    |
| `token refresh failed`                     | anything else                                               |

## Test

    uv run pytest
    uv run ruff check .

## Status

Milestone M1: skeleton, settings from the environment, `/health`. The tagging
endpoint (`POST /tag`) arrives with M2.

Note: the plan refers to the module as `app.main`; this project is a
`src`-layout package built by uv_build, so the same application lives in
`tagger.main` and is started with `uv run uvicorn tagger.main:app`.
