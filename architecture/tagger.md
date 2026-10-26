# Piano di realizzazione: tagger di immagini automatico (CLIP / SigLIP + captioning)

## Obiettivo

Costruire un tagger di immagini che, data una foto, restituisca una lista di tag
descrittivi senza che l'utente debba definire un vocabolario.

L'utente scatta una foto dal browser, la foto viene inviata al backend, il backend
calcola i tag e li restituisce alla UI, che li mostra ordinati per rilevanza.

Chiariamo un punto tecnico importante, perche determina l'architettura: CLIP e SigLIP
sono modelli di tipo retrieval, cioe confrontano l'immagine con un elenco di testi
candidati e restituiscono un punteggio per ciascuno. Non sono in grado di inventare
etichette dal nulla. Per avere tag senza che l'utente definisca un vocabolario
esistono due strade, e il piano le prevede entrambe:

1. Motore A - vocabolario interno al backend. Il servizio spedisce con se un elenco
   di tag curato (es. 1000-5000 etichette semplici in inglese, con eventuale
   traduzione italiana in uscita). L'utente non definisce nulla: manda solo la foto.
   Veloce, deterministico, economico. E il percorso predefinito.
2. Motore B - captioning generativo. Un modello image-to-text (es. BLIP, Florence-2,
   oppure un piccolo VLM) produce una descrizione libera dell'immagine, da cui si
   estraggono le etichette. Non e limitato dall'elenco interno, ma e piu lento e piu
   rumoroso. Opzionale, attivabile per richiesta.

I tag prodotti dal motore B vengono poi ri-punteggiati con CLIP/SigLIP contro
l'immagine, cosi ogni tag esce comunque con uno score confrontabile con quelli del
motore A. In questo modo la UI riceve sempre lo stesso formato.

Nessuna fase di training in entrambi i casi.

Flusso dei dati:

1. La Web UI cattura la foto e la invia al backend come multipart/form-data.
2. Il backend sceglie il motore (A, B oppure entrambi) in base alla richiesta.
3. Motore A: calcola l'embedding dell'immagine e lo confronta con gli embedding del
   vocabolario interno, gia precalcolati all'avvio.
4. Motore B: genera una descrizione, ne estrae le etichette e le ri-punteggia con
   CLIP/SigLIP.
5. Il backend unisce, deduplica e ordina i tag, poi li restituisce in JSON.
6. La UI mostra i tag all'utente.

---

## Contratto API (riferimento per UI e backend)

### POST /tag

Richiesta in multipart/form-data:

| Campo     | Tipo   | Obbligatorio | Note                                                   |
|-----------|--------|--------------|--------------------------------------------------------|
| image     | file   | si           | JPEG, PNG o WebP, max circa 10 MB                      |
| mode      | string | no           | auto (default), vocab, caption                         |
| top_k     | int    | no           | default 10                                             |
| threshold | float  | no           | default 0.0 (nessun filtro)                            |
| lang      | string | no           | lingua delle etichette in uscita (default it)          |

Nota: il campo vocab e stato rimosso. Il client non invia piu alcun vocabolario.
La lista dei tag e una responsabilita del backend.

Significato di mode:

1. vocab - solo motore A, il piu veloce.
2. caption - solo motore B, etichette libere.
3. auto - motore A, arricchito dal motore B se il modello di captioning e caricato;
   altrimenti si comporta come vocab.

Risposta 200, corpo JSON con questa forma:

- model: stringa, nome del modello di embedding usato
- caption_model: stringa oppure null, modello di captioning usato
- tags: lista di oggetti con i campi tag (stringa), score (float) e source
  (stringa: vocab oppure caption)
- caption: stringa oppure null, la descrizione grezza prodotta dal motore B
- timing_ms: oggetto con i tempi di preprocess, encode_image, scoring e caption

Esempio concettuale: tre tag, "cane" con score 0.91 da vocab, "prato" con score 0.43
da vocab, "palla rossa" con score 0.38 da caption.

Errori:

| Codice | Significato                                      |
|--------|--------------------------------------------------|
| 400    | file non valido oppure mode non riconosciuto     |
| 413    | file troppo grande                               |
| 422    | payload non conforme allo schema                 |
| 500    | errore interno del backend                       |

### GET /health

Restituisce lo stato del servizio, i modelli caricati e la dimensione del
vocabolario interno.

---

## Vocabolario interno (lato backend)

Il vocabolario non e piu un input dell'utente, ma un asset del servizio.

1. File dati versionato nel repository, es. app/data/tags_it.json, con struttura a
   categorie (soggetti, animali, ambienti, oggetti, azioni, colori, materiali).
2. Ogni voce puo avere sinonimi e la traduzione italiana usata in uscita, per esempio
   entry con campi: id, en, it, category, synonyms.
3. Dimensione consigliata: partire da 300-500 tag ben scelti e generici, crescere
   fino a qualche migliaio solo se misurato utile. Troppi tag peggiorano la
   precisione e allungano lo scoring.
4. Regole di qualita: etichette brevi, concrete e non sovrapposte ("cane" e non
   "animale domestico a quattro zampe"); niente duplicati; sinonimi gestiti per
   evitare che lo stesso concetto compaia due volte nei risultati.
5. Script di validazione offline che controlla duplicati, lunghezze, categorie
   mancanti e coerenza delle traduzioni. Non e un test automatico della pipeline:
   e un controllo dell'asset dati, eseguibile a mano prima di un rilascio.

---

## Parte backend

### 1. Skeleton FastAPI

1. Progetto Python con pyproject.toml (o requirements.txt) e dipendenze:
   fastapi, uvicorn, torch, transformers, pillow, numpy, pydantic-settings.
2. Dipendenze opzionali per il motore B: transformers con i pesi di captioning
   (BLIP o Florence-2), caricate solo se CAPTION_ENABLED e true.
3. Modulo app/main.py con istanza FastAPI e middleware CORS limitato all'origine
   della UI.
4. Avvio con uvicorn app.main:app con host e porta configurabili.

### 2. Caricamento dei modelli

1. Caricare i modelli nell'evento lifespan, non a ogni richiesta, cosi l'avvio
   fallisce subito in caso di configurazione errata.
2. Embedding: transformers con AutoProcessor e AutoModel, con checkpoint
   configurabile (es. google/siglip-base-patch16-224 oppure
   openai/clip-vit-base-patch32).
3. Selezione device: cuda se disponibile, altrimenti cpu; float16 su GPU e float32
   su CPU.
4. Chiamare model.eval() e usare torch.inference_mode() per tutte le inferenze.
5. Motore B, se abilitato: caricare il modello di captioning nello stesso lifespan,
   con la stessa politica di device e dtype.
6. Parametri esposti via variabili d'ambiente: MODEL_NAME, DEVICE, DTYPE,
   MAX_IMAGE_SIZE, VOCAB_PATH, CAPTION_ENABLED, CAPTION_MODEL_NAME.

### 3. Precalcolo degli embedding del vocabolario (novita importante)

Poiche il vocabolario e fisso e appartiene al backend, il lavoro testuale si fa una
volta sola all'avvio, non a ogni richiesta.

1. All'avvio leggere il vocabolario interno e costruire i prompt con il template
   adatto al modello (per CLIP "a photo of a X"; per SigLIP il template conta meno).
2. Calcolare gli embedding testuali in batch, normalizzarli L2 e tenerli in memoria
   come tensore unico.
3. Salvare opzionalmente su disco una cache degli embedding con chiave composta da
   nome modello piu hash del vocabolario, per ridurre il tempo di avvio.
4. Alla richiesta il costo testuale e quindi zero: si calcola solo l'embedding
   dell'immagine.

### 4. Preprocessing dell'immagine

1. Leggere l'upload in memoria, aprire con PIL e convertire in RGB.
2. Verificare dimensione del file e MIME lato server, senza fidarsi del client.
3. Applicare il processor del modello (resize, center crop, normalizzazione).
4. Limitare risoluzioni enormi con un downscale preventivo per evitare abusi di
   memoria.

### 5. Scoring del motore A (vocabolario interno)

1. Calcolare l'embedding dell'immagine e normalizzarlo.
2. CLIP: similarita coseno, poi logits moltiplicati per logit_scale e softmax.
3. SigLIP: il modello e addestrato con loss sigmoide, quindi usare sigmoid sui logits
   per punteggi indipendenti per tag, soluzione migliore per il multi-label.
4. Ordinare per punteggio, applicare top_k e threshold, mappare gli id in etichette
   nella lingua richiesta.
5. Deduplicare i sinonimi: se due etichette del vocabolario puntano allo stesso
   concetto, tenere solo il punteggio migliore.

### 6. Motore B (captioning generativo, opzionale)

1. Generare una descrizione breve dell'immagine con il modello di captioning
   (beam search corta, max 30-40 token).
2. Estrarre le etichette dalla descrizione con regole semplici: rimozione di stop
   word, sostantivi e aggettivi, bigrammi significativi (es. "palla rossa").
3. Ripunteggiare ogni etichetta candidata con CLIP/SigLIP contro l'immagine, riusando
   lo stesso percorso di scoring del motore A. Questo normalizza i punteggi e scarta
   le etichette allucinate (score basso).
4. Applicare la soglia anche a queste etichette; il campo source vale caption.
5. Limite di sicurezza sul numero di etichette estratte per richiesta.

### 7. Fusione dei risultati

1. Unire le liste prodotte dai due motori.
2. Deduplicare per etichetta normalizzata (lowercase, trim, rimozione dei sinonimi
   gia mappati).
3. In caso di collisione tenere lo score piu alto e la source piu informativa
   (caption).
4. Riordinare per punteggio decrescente e applicare top_k una sola volta in fondo.
5. Restituire anche la caption grezza, utile per debug e per mostrare all'utente una
   descrizione dell'immagine.

### 8. Endpoint

1. POST /tag come da contratto: parsing di UploadFile, mode, top_k, threshold e lang,
   con validazione Pydantic dei parametri scalari.
2. Validare mode contro i valori ammessi; se caption non e abilitato lato server e
   mode vale caption, restituire 400 con messaggio esplicito.
3. GET /health: stato del servizio, modelli caricati e dimensione del vocabolario.
4. GET /tags/categories: elenco delle categorie del vocabolario interno, utile alla
   UI per raggruppare i risultati.
5. Gestione errori centralizzata con HTTPException e messaggi chiari.

### 9. Prestazioni e deploy

1. Con SigLIP base su GPU, il costo per immagine e di pochi millisecondi; su CPU
   restare su checkpoint base e non usare varianti large.
2. Il motore B e opzionale proprio perche costa decine o centinaia di millisecondi in
   piu: tenerlo disattivabile via CAPTION_ENABLED.
3. Predisporre un predict_batch interno per elaborare piu immagini in futuro.
4. Abilitare torch.compile o export ONNX solo dopo aver misurato la latenza reale.
5. Un solo worker con GPU (un processo per GPU); su CPU valutare piu worker.
6. Dockerfile con dipendenze bloccate e healthcheck su /health.
7. Rate limiting leggero per IP e limite di dimensione richiesta a livello di reverse
   proxy.

---

## Parte UI

La UI non gestisce piu alcun vocabolario: nessun editor, nessun import/export di tag.
L'utente fotografa e riceve i tag.

### 1. Struttura della pagina

1. Sezione camera: anteprima live (elemento video), pulsante di scatto, pulsante per
   cambiare fotocamera (front/back), pulsante per caricare un file come fallback.
2. Sezione anteprima: miniatura dello scatto con pulsanti "ripeti" e "analizza".
3. Sezione risultati: lista dei tag con punteggio e barra, filtro per soglia,
   eventuale descrizione dell'immagine (caption) se presente.
4. Controllo "dettagliato": interruttore che mappa mode tra vocab e auto, per
   scegliere tra risultato rapido e risultato piu ricco. Nascosto se il backend non
   ha il captioning abilitato.

### 2. Acquisizione della foto

1. Richiedere getUserMedia con facingMode environment all'apertura della sezione
   camera; gestire il caso di permesso negato mostrando il fallback file.
2. Disegnare il frame corrente su un canvas allo scatto.
3. Ridimensionare lato client (lato massimo circa 1024 px) e comprimere in JPEG
   con toBlob e qualita circa 0.85 per ridurre il payload.
4. Passare il Blob risultante al flusso di upload.

### 3. Upload e stati

1. Costruire un FormData con image, mode, top_k e threshold. Nessun vocabolario.
2. Effettuare una fetch POST verso /tag con il FormData come body.
3. Gestire una macchina a stati esplicita:
   idle, capturing, ready, uploading, success, error.
4. Mostrare uno spinner o overlay durante l'upload e disabilitare i pulsanti per
   evitare richieste concorrenti.
5. Timeout client differenziato: circa 30 s in mode vocab, circa 60 s in mode auto o
   caption, con AbortController e messaggio di errore leggibile.
6. Pulsante "riprova" in caso di errore.

### 4. Visualizzazione dei risultati

1. Ordinare i tag per punteggio decrescente.
2. Mostrare una barra proporzionale al punteggio accanto a ogni tag.
3. Distinguere visivamente, se utile, i tag provenienti da caption (es. con un
   contrassegno leggero), senza appesantire l'interfaccia.
4. Slider per la soglia minima: filtrare lato client senza nuove chiamate.
5. Raggruppare i tag per categoria, se GET /tags/categories e disponibile, con un
   controllo per passare alla lista piatta.
6. Stato vuoto esplicito quando nessun tag supera la soglia, con suggerimento di
   abbassarla o di attivare la modalita dettagliata.

### 5. Robustezza e accessibilita

1. Layout responsive: camera e risultati a colonna su mobile, affiancati su desktop.
2. aria-live sulla sezione risultati per annunciare l'esito.
3. Etichette accessibili su tutti i controlli, focus visibile, navigazione da tastiera.
4. Messaggi di errore distinti per permesso camera negato, upload fallito, backend
   non raggiungibile e backend senza captioning quando richiesto.
5. Pulizia dello stream della camera (track.stop) quando si cambia sezione o si
   smonta il componente.

---

## Scelte tecniche

1. Vocabolario interno contro captioning: senza un elenco candidato CLIP e SigLIP non
   possono produrre etichette, quindi il vocabolario interno resta il percorso
   predefinito. Il captioning aggiunge liberta ma con costi e rumore: per questo e
   opzionale.
2. Ri-punteggio delle etichette da caption: e il modo piu semplice per dare alle
   etichette libere uno score confrontabile e per scartare le allucinazioni, senza
   dover addestrare nulla.
3. CLIP contro SigLIP: SigLIP generalizza meglio in zero-shot su vocabolari
   arbitrari (loss sigmoide, punteggi indipendenti) ed e la scelta consigliata per il
   multi-label. Resta configurabile via MODEL_NAME.
4. Precalcolo degli embedding testuali all'avvio: elimina completamente il costo
   testuale per richiesta ed e possibile proprio perche il vocabolario non dipende
   piu dall'utente.
5. Calibrazione: i punteggi non sono probabilita calibrate, quindi usare la soglia
   come parametro di UX e non come valore assoluto.
6. Lingua in uscita: il vocabolario interno porta con se le traduzioni, cosi la UI
   mostra etichette italiane anche se i prompt per il modello sono in inglese.

---

## Milestone

1. M1 - Skeleton backend: FastAPI avviato, modello di embedding caricato, /health
   funzionante.
2. M2 - Vocabolario interno e precalcolo: file dati, script di validazione,
   embedding testuali calcolati all'avvio e messi in cache.
3. M3 - Tagging: /tag in mode vocab con scoring, top_k, threshold e mappatura in
   italiano.
4. M4 - UI minima: scatto da camera, upload e visualizzazione dei tag. Nessun
   vocabolario lato client.
5. M5 - Motore B: captioning opzionale, estrazione etichette, ri-punteggio e fusione
   dei risultati.
6. M6 - Rifiniture: soglie, stati di errore, responsive, accessibilita, controllo
   dettagliato nella UI e configurazione tramite variabili d'ambiente.
