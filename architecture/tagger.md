# Piano di realizzazione: tagger di immagini automatico (Google Cloud Vision)

## Obiettivo

Costruire un tagger di immagini che, data una foto, restituisca una lista di tag
descrittivi senza che l'utente debba definire un vocabolario.

L'utente scatta una foto dal browser, la foto viene inviata al backend, il backend
calcola i tag e li restituisce alla UI, che li mostra ordinati per rilevanza.

Chiariamo un punto tecnico importante, perche determina l'architettura. Nella versione
precedente di questo piano il tagging era fatto in casa con CLIP/SigLIP: quei modelli
sono di tipo retrieval, cioe confrontano l'immagine con un elenco di testi candidati e
restituiscono un punteggio per ciascuno, e non sanno inventare etichette dal nulla.
Serviva quindi un vocabolario interno al backend e un secondo motore di captioning per
avere etichette libere.

Con Google Cloud Vision il problema si sposta sul fornitore. Label Detection e un
classificatore multi-etichetta gia addestrato: data un'immagine restituisce
direttamente le etichette con un punteggio, senza che noi si debba fornire un
vocabolario. Vengono meno, di conseguenza:

1. il vocabolario interno e il suo file dati;
2. il precalcolo degli embedding testuali all'avvio e la relativa cache;
3. il motore di captioning e la fase di ri-punteggio delle etichette libere;
4. le dipendenze transformers, torch e i pesi dei modelli locali.

Cloud Vision non produce descrizioni libere dell'immagine (non e un modello
image-to-text): il motore B e il campo caption della risposta vengono quindi rimossi.
Se in futuro servira una descrizione discorsiva, andra aggiunto un fornitore diverso,
in una fase separata.

Il backend resta comunque un passaggio obbligato, per tre motivi: le credenziali verso
Google non devono mai finire nel browser, il payload va validato e ridotto lato
server, e i punteggi grezzi del fornitore vanno normalizzati e fusi in un formato
stabile per la UI.

Flusso dei dati:

1. La Web UI cattura la foto e la invia al backend come multipart/form-data.
2. Il backend valida file e parametri e decide quali feature di Cloud Vision
   interrogare, in base al campo mode.
3. Il backend chiama l'API Vision con le feature scelte e gli hint di lingua.
4. Il backend normalizza i punteggi, deduplica, applica threshold e top_k.
5. Il backend restituisce i tag in JSON.
6. La UI mostra i tag all'utente.

---

## Contratto API (riferimento per UI e backend)

### POST /tag

Richiesta in multipart/form-data:

| Campo     | Tipo   | Obbligatorio | Note                                                   |
|-----------|--------|--------------|--------------------------------------------------------|
| image     | file   | si           | JPEG, PNG o WebP, max circa 10 MB                      |
| mode      | string | no           | auto (default), labels, objects                        |
| top_k     | int    | no           | default 10                                             |
| threshold | float  | no           | default 0.0 (nessun filtro)                            |
| lang      | string | no           | lingua delle etichette in uscita (default it)          |

Nota: il campo vocab e stato rimosso. Il client non invia alcun vocabolario: la lista
dei tag e una responsabilita del fornitore.

Significato di mode:

1. labels - solo Label Detection, il piu veloce e il piu economico.
2. objects - Label Detection piu Object Localization, utile quando l'immagine contiene
   soggetti distinti che vale la pena isolare.
3. auto - tutte le feature abilitate lato server (labels, objects e, se attiva, web
   detection). E il comportamento predefinito.

Risposta 200, corpo JSON con questa forma:

- provider: stringa, sempre google-cloud-vision
- features: lista delle feature interrogate, es. labels, objects
- tags: lista di oggetti con i campi tag (stringa), score (float) e source
  (stringa: label oppure object)
- timing_ms: oggetto con i tempi di preprocess, upstream e scoring

Esempio concettuale: tre tag, "cane" con score 0.91 da label, "prato" con score 0.43
da label, "palla" con score 0.38 da object.

Errori:

| Codice | Significato                                              |
|--------|----------------------------------------------------------|
| 400    | file non valido oppure mode non riconosciuto             |
| 413    | file troppo grande                                       |
| 422    | payload non conforme allo schema                         |
| 429    | quota del fornitore esaurita (propagata al client)       |
| 502    | risposta non valida o errore del fornitore               |
| 503    | fornitore non raggiungibile o timeout                    |
| 500    | errore interno del backend                               |

### GET /health

Restituisce lo stato del servizio, la raggiungibilita delle credenziali Google, il
progetto configurato e le feature abilitate. Non espone misure del vocabolario, che
non esiste piu.

---

## Etichette e lingua (lato backend)

Cloud Vision restituisce le etichette in inglese per default. Il campo lang del
contratto viene mappato su imageContext.languageHints, cosi le etichette tornano gia
localizzate e non serve alcuna tabella di traduzione.

1. Elenco delle lingue supportate: it, en (estendibile senza modifiche di codice,
   basta passare il valore richiesto e lasciare che il fornitore risponda 400 se non
   supportato).
2. Se il fornitore non riconosce la lingua richiesta, il backend ricade su inglese e
   lo segnala nel log, invece di far fallire la richiesta.
3. Le etichette restano comunque nomi comuni brevi e concreti: non c'e piu un asset
   dati da curare, quindi non c'e piu bisogno dello script di validazione del
   vocabolario.

Resta un unico piccolo asset locale, opzionale: app/data/tag_aliases.json, una mappa
di normalizzazione usata solo per la deduplica (per esempio cane/cani,
auto/automobile). Non e input dell'utente ne vocabolario: se manca, la deduplica usa
la sola normalizzazione testuale (minuscole, trim, rimozione della punteggiatura).

---

## Parte backend

### 1. Skeleton FastAPI con uv

1. Gestione delle dipendenze con uv, non con pip a mano:
   - `uv init` e `uv add fastapi uvicorn[standard] google-cloud-vision pillow
     pydantic-settings` per le dipendenze di runtime;
   - `uv add --dev pytest pytest-asyncio httpx ruff` per il resto;
   - `uv.lock` versionato nel repository, cosi le build sono riproducibili.
2. Avvio in locale con `uv run uvicorn app.main:app --host 0.0.0.0 --port 8000`;
   negli script e nella CI usare sempre `uv run`, mai un virtualenv attivato a mano.
3. Python 3.11 o superiore, fissato in pyproject.toml (requires-python) e in
   .python-version per uv.
4. Modulo app/main.py con istanza FastAPI e middleware CORS limitato all'origine
   della UI.
5. Dockerfile basato su immagine con uv, con `uv sync --frozen` per installare
   esattamente le versioni del lock.
6. Variabili d'ambiente lette con pydantic-settings, documentate in .env.example.

### 2. Client Cloud Vision

1. Un solo ImageAnnotatorClient, costruito nell'evento lifespan e chiuso allo
   shutdown; non un client per richiesta.
2. Autenticazione tramite Application Default Credentials: in locale
   GOOGLE_APPLICATION_CREDENTIALS punta al file del service account, in produzione si
   usa il service account collegato al servizio (Workload Identity su GKE o Cloud
   Run). Nessuna chiave nel repository.
3. Service account con permessi minimi: solo vision.images.annotate (custom role),
   piu il ruolo di consumer necessario per la quota project se previsto.
4. Il client della libreria e sincrono: le chiamate vanno eseguite fuori dal loop,
   con asyncio.to_thread, per non bloccare il server.
5. Timeout configurabile lato client e retry con backoff esponenziale e jitter sui
   soli errori transitori (429, 500, 503, deadline exceeded).
6. Parametri esposti via variabili d'ambiente: GOOGLE_CLOUD_PROJECT,
   GOOGLE_APPLICATION_CREDENTIALS, VISION_TIMEOUT_MS, VISION_MAX_RESULTS,
   VISION_ENABLE_OBJECTS, VISION_ENABLE_WEB, MAX_IMAGE_SIZE, TAG_ALIAS_PATH.

### 3. Preprocessing dell'immagine

1. Leggere l'upload in memoria, aprire con PIL e convertire in RGB.
2. Correggere l'orientamento usando i metadati EXIF prima dell'invio, altrimenti le
   foto da smartphone escono ruotate e peggiorano i risultati.
3. Verificare dimensione del file e MIME lato server, senza fidarsi del client.
4. Downscale preventivo oltre MAX_IMAGE_SIZE per contenere il payload verso il
   fornitore: la latenza di rete dipende dalla dimensione del file.
5. Ricomprimere in JPEG solo se il downscale e stato applicato, per non degradare
   inutilmente un'immagine gia piccola.

### 4. Costruzione della richiesta

1. Costruire un singolo vision.Image con il contenuto in memoria.
2. Impostare le feature in base a mode: LABEL_DETECTION sempre, OBJECT_LOCALIZATION
   solo per objects e auto, WEB_DETECTION solo per auto e solo se VISION_ENABLE_WEB.
3. Impostare max_results per feature a un valore piu alto del top_k richiesto (default
   VISION_MAX_RESULTS, es. 30), per avere margine dopo threshold, deduplica e fusione.
4. Impostare image_context.language_hints con la lingua richiesta.
5. Inoltrare timeout e retry al client.

### 5. Normalizzazione dei punteggi

Il fornitore non restituisce un unico campo di punteggio: va scelto esplicitamente.

1. Label Detection: usare topicality se presente, altrimenti score. Il primo misura
   quanto l'etichetta e centrale per l'immagine, il secondo la confidenza; topica lity
   e piu adatto a ordinare i risultati.
2. Object Localization: usare confidence, piu bounding box e nome dell'oggetto.
3. Le etichette con score assente o non numerico vanno scartate, non valorizzate a
   zero.
4. Non normalizzare ulteriormente i punteggi tra loro: il contratto espone il valore
   del fornitore, che resta confrontabile con se stesso ma non e una probabilita
   calibrata.

### 6. Fusione dei risultati

1. Unire le liste prodotte dalle feature interrogate.
2. Deduplicare per etichetta normalizzata (minuscole, trim, punteggiatura rimossa) e
   per alias, quando tag_aliases.json e presente.
3. In caso di collisione tenere lo score piu alto e la source piu informativa
   (object).
4. Scartare i casi in cui la stessa etichetta compare come label e come object con
   punteggi molto diversi: e rumore, non un segnale.
5. Riordinare per punteggio decrescente, applicare threshold e top_k una sola volta
   in fondo.
6. Trattare il risultato vuoto come esito legittimo, non come errore.

### 7. Endpoint

1. POST /tag come da contratto: parsing di UploadFile, mode, top_k, threshold e lang,
   con validazione Pydantic dei parametri scalari.
2. Validare mode contro i valori ammessi e rifiutare con 400 quelli non riconosciuti.
3. Rifiutare con 400 mode objects o auto se la feature e disabilitata lato server, con
   messaggio esplicito, invece di degradare silenziosamente.
4. GET /health: stato del servizio, verifica delle credenziali (token cached, non una
   chiamata Vision a ogni probe) e feature abilitate.
5. Gestione errori centralizzata: mappare le eccezioni del client Google sui codici
   del contratto (429 e 503 in particolare), senza far trapelare stack trace o
   dettagli delle credenziali.
6. Nessun endpoint di categorie: Cloud Vision non espone categorie.

### 8. Prestazioni, costi e deploy

1. Il costo per immagine e una chiamata di rete all'ordine delle centinaia di
   millisecondi; sull'ordine dei dieci millisecondi c'e solo il preprocessing.
2. Ogni chiamata a Cloud Vision e fatturata per feature e per immagine: interrogare
   solo le feature necessarie e non abilitare objects o web per default senza motivo.
3. Caching applicativo opzionale: hash del contenuto piu parametri come chiave, con
   TTL breve, utile quando la UI richiede la stessa foto con soglie diverse.
4. Batch in futuro: l'API accetta piu immagini nella stessa richiesta (fino a 16 in
   files:annotate, migliaia con asyncBatchAnnotate). Predisporre un predict_batch
   interno, non esporlo subito.
5. Rispettare le quote del progetto; davanti al servizio un rate limit per IP e un
   limite di dimensione richiesta a livello di reverse proxy.
6. Un solo processo e sufficiente, il collo di bottiglia e il fornitore. Su CPU
   restare su un numero contenuto di worker e affidarsi all'asincronia.
7. Deploy consigliato su Cloud Run con service account dedicato, healthcheck su
   /health, e log strutturati con request id per correlare le chiamate al fornitore.

---

## Parte UI

La UI non gestisce alcun vocabolario: nessun editor, nessun import/export di tag.
L'utente fotografa e riceve i tag.

### 1. Struttura della pagina

1. Sezione camera: anteprima live (elemento video), pulsante di scatto, pulsante per
   cambiare fotocamera (front/back), pulsante per caricare un file come fallback.
2. Sezione anteprima: miniatura dello scatto con pulsanti "ripeti" e "analizza".
3. Sezione risultati: lista dei tag con punteggio e barra, filtro per soglia.
4. Controllo "dettagliato": interruttore che mappa mode tra labels e auto, per
   scegliere tra risultato rapido e risultato piu ricco. Nascosto se il backend ha
   objects disabilitato.

### 2. Acquisizione della foto

1. Richiedere getUserMedia con facingMode environment all'apertura della sezione
   camera; gestire il caso di permesso negato mostrando il fallback file.
2. Disegnare il frame corrente su un canvas allo scatto.
3. Ridimensionare lato client (lato massimo circa 1024 px) e comprimere in JPEG con
   toBlob e qualita circa 0.85 per ridurre il payload di rete.
4. Passare il Blob risultante al flusso di upload.

### 3. Upload e stati

1. Costruire un FormData con image, mode, top_k e threshold. Nessun vocabolario.
2. Effettuare una fetch POST verso /tag con il FormData come body.
3. Gestire una macchina a stati esplicita: idle, capturing, ready, uploading,
   success, error.
4. Mostrare uno spinner o overlay durante l'upload e disabilitare i pulsanti per
   evitare richieste concorrenti.
5. Timeout client unico di circa 20 s (la latenza e dominata dalla rete verso il
   fornitore), con AbortController e messaggio di errore leggibile.
6. Pulsante "riprova" in caso di errore.

### 4. Visualizzazione dei risultati

1. Ordinare i tag per punteggio decrescente.
2. Mostrare una barra proporzionale al punteggio accanto a ogni tag.
3. Distinguere visivamente, se utile, i tag provenienti da object (es. con un
   contrassegno leggero), senza appesantire l'interfaccia.
4. Slider per la soglia minima: filtrare lato client senza nuove chiamate.
5. Nessun raggruppamento per categoria: il fornitore non le espone. La lista resta
   piatta e ordinata per punteggio.
6. Stato vuoto esplicito quando nessun tag supera la soglia, con suggerimento di
   abbassarla o di attivare la modalita dettagliata.

### 5. Robustezza e accessibilita

1. Layout responsive: camera e risultati a colonna su mobile, affiancati su desktop.
2. aria-live sulla sezione risultati per annunciare l'esito.
3. Etichette accessibili su tutti i controlli, focus visibile, navigazione da tastiera.
4. Messaggi di errore distinti per permesso camera negato, upload fallito, backend non
   raggiungibile, quota esaurita (429) e fornitore non disponibile (503).
5. Pulizia dello stream della camera (track.stop) quando si cambia sezione o si
   smonta il componente.

---

## Scelte tecniche

1. Cloud Vision contro modello locale: il fornitore elimina vocabolario, pesi,
   precalcolo e GPU, e gestisce la localizzazione delle etichette nativamente. In
   cambio si accettano latenza di rete, costo per immagine e dipendenza dal fornitore.
2. Assenza di captioning: Cloud Vision non e un modello image-to-text. Meglio
   rimuovere il campo caption dal contratto che restituire un campo sempre nullo; se
   servira, si aggiungera un secondo fornitore con contratto esteso.
3. Feature selezionabili invece di un unico comportamento: labels e il percorso
   rapido ed economico, objects aggiunge precisione sui soggetti, auto e la comodita.
4. Precalcolo degli embedding: non serve piu, era possibile solo perche il
   vocabolario era interno. Il costo per richiesta ora e una singola chiamata HTTP.
5. Calibrazione: i punteggi non sono probabilita calibrate, quindi usare la soglia
   come parametro di UX e non come valore assoluto.
6. Lingua in uscita: delegata a languageHints, senza asset di traduzione da
   mantenere.
7. Alias locali ridotti al minimo: servono solo a evitare duplicati evidenti, non a
   definire cosa il tagger puo riconoscere.

---

## Milestone

1. M1 - Skeleton backend: progetto inizializzato con uv (pyproject.toml,
   .python-version, uv.lock versionato), FastAPI avviato con `uv run uvicorn`,
   impostazioni via variabili d'ambiente e /health che verifica le credenziali Google.
2. M2 - Tagging di base: POST /tag in mode labels, preprocessing dell'immagine,
   normalizzazione dei punteggi, threshold, top_k e mappatura della lingua.
3. M3 - Feature aggiuntive: Object Localization, mode objects e auto, fusione e
   deduplica dei risultati, alias locali.
4. M4 - UI minima: scatto da camera, upload e visualizzazione dei tag. Nessun
   vocabolario lato client.
5. M5 - Affidabilita: retry con backoff, mappatura degli errori del fornitore, quota
   e rate limiting, log strutturati con request id.
6. M6 - Rifiniture: soglie, stati di errore, responsive, accessibilita, controllo
   dettagliato nella UI, caching applicativo e deploy su Cloud Run con service account
   dedicato.
