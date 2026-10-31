# environment

source .venv/bin/activate

# tagger

Servizio di tagging automatico delle immagini basato su Google Cloud Vision:
riceve una foto via `multipart/form-data` e restituisce una lista di tag ordinati
per punteggio.

Il contratto completo (parametri, codici di errore, significato di `mode`) è
descritto in `../architecture/tagger.md`.

## Requisiti

- Python 3.12 (la versione è fissata in `.python-version`, uv la usa da solo)
- [uv](https://docs.astral.sh/uv/)
- Credenziali Google Cloud con il ruolo minimo `vision.images.annotate`

## Setup locale

    cp .env.example .env

Valorizzare almeno `GOOGLE_CLOUD_PROJECT` e `GOOGLE_APPLICATION_CREDENTIALS`
(percorso del file del service account). Le stesse variabili possono essere
esportate nell'ambiente invece che scritte nel `.env`.

Installare le dipendenze esattamente come sono nel lock:

    uv sync

Avviare il servizio:

    uv run uvicorn tagger.main:app --host 0.0.0.0 --port 8000 --reload

## Test e lint

    uv run pytest
    uv run ruff check .

## Docker

    docker build -t tagger .
    docker run --rm -p 8000:8000 --env-file .env tagger

L'immagine esegue `uv sync --frozen`: se `pyproject.toml` cambia, il lock va
rigenerato con `uv lock` e ricommittato, altrimenti la build fallisce.

## Endpoint

`GET /health`
    Stato del servizio, raggiungibilità delle credenziali, progetto
    configurato e feature abilitate. Non chiama Vision a ogni probe.

`POST /tag`
    Campi: `image` (obbligatorio), `mode` (`auto` | `labels` | `objects`),
    `top_k`, `threshold`, `lang`. I campi omessi usano i default di
    configurazione (`DEFAULT_TOP_K`, `DEFAULT_THRESHOLD`, `DEFAULT_LANG`).

    Codici: 400 file o `mode` non validi, 413 file troppo grande,
    422 parametri fuori schema, 429 quota esaurita, 502 risposta del
    fornitore non valida, 503 fornitore non raggiungibile.

## Note

- Il processo tiene un solo `ImageAnnotatorClient`, creato nel `lifespan` e
  chiuso allo shutdown; le chiamate girano in `asyncio.to_thread`.
- Se le credenziali mancano, il servizio parte comunque e `/health` riporta
  `credentials_ok: false` invece di far fallire il boot.
