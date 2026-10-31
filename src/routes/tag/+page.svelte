<script lang="ts">
	import { onDestroy, onMount } from 'svelte';
	import type { PageData } from './$types';

	let { data }: { data: PageData } = $props();

	type Phase = 'idle' | 'capturing' | 'ready' | 'uploading' | 'success' | 'error';

	interface Tag {
		tag: string;
		score: number;
		source: string;
	}

	/** Longest side (px) of the frame sent to the backend. */
	const MAX_CAPTURE_DIMENSION = 1024;
	/** JPEG quality used to encode the captured frame. */
	const CAPTURE_QUALITY = 0.85;
	/** Same limit as `MAX_IMAGE_SIZE` on the tagger side. */
	const MAX_UPLOAD_BYTES = 10 * 1024 * 1024;
	/** The provider dominates latency: leave room for a slow Vision call. */
	const UPLOAD_TIMEOUT_MS = 20_000;
	/**
	 * Ask for more tags than the UI shows by default, so the client-side
	 * threshold slider still has something to reveal. It does not cost more:
	 * the backend already asks Cloud Vision for `VISION_MAX_RESULTS` (30)
	 * annotations per feature.
	 */
	const REQUESTED_TOP_K = 30;

	/**
	 * Explicit UI state machine:
	 *   idle       → camera live (or file fallback), waiting for a shot
	 *   capturing  → camera stream being (re)acquired
	 *   ready      → frame captured, preview shown, "Analizza" available
	 *   uploading  → POST /api/tag in flight
	 *   success    → tags received
	 *   error      → request failed, retry available
	 */
	let phase = $state<Phase>('idle');

	// Camera
	let videoEl = $state<HTMLVideoElement>();
	let stream = $state<MediaStream>();
	let facingMode = $state<'environment' | 'user'>('environment');
	let cameraError = $state('');

	// Preview: the object URL is reactive, the blob behind it is not.
	let previewUrl = $state('');
	let previewBlob: Blob | undefined;

	// Results
	let tags = $state<Tag[]>([]);
	let uploadError = $state('');
	let threshold = $state(0);

	// Options: the toggle only exists when the backend exposes `objects`.
	let detailed = $state(false);
	const mode = $derived(detailed && data.objectsEnabled ? 'auto' : 'labels');
	const visibleTags = $derived(tags.filter((tag) => tag.score >= threshold));

	function clamp01(value: number): number {
		return Math.min(1, Math.max(0, value));
	}

	function percent(value: number): number {
		return Math.round(clamp01(value) * 100);
	}

	// --- Camera ------------------------------------------------------------

	/**
	 * Attaches the MediaStream to the <video> element. Written as an action so
	 * the stream is re-attached when the element remounts: the preview replaces
	 * the live view, and "Ripeti" brings the video back.
	 */
	function attachStream(node: HTMLVideoElement, src: MediaStream | undefined) {
		node.srcObject = src ?? null;
		if (src) void node.play().catch(() => {});

		return {
			update(next: MediaStream | undefined) {
				node.srcObject = next ?? null;
				if (next) void node.play().catch(() => {});
			},
			destroy() {
				node.srcObject = null;
			}
		};
	}

	function stopCamera() {
		stream?.getTracks().forEach((track) => track.stop());
		stream = undefined;
	}

	function describeCameraError(e: unknown): string {
		if (e instanceof DOMException) {
			switch (e.name) {
				case 'NotAllowedError':
				case 'PermissionDeniedError':
					return 'Permesso fotocamera negato. Abilitalo nelle impostazioni del browser, oppure carica un’immagine dal dispositivo.';
				case 'NotFoundError':
				case 'DevicesNotFoundError':
					return 'Nessuna fotocamera trovata. Carica un’immagine dal dispositivo.';
				case 'NotReadableError':
				case 'TrackStartError':
					return 'La fotocamera è occupata da un’altra applicazione. Chiudila e riprova.';
				case 'OverconstrainedError':
					return 'La fotocamera non supporta la modalità richiesta. Riprova o carica un’immagine.';
				case 'SecurityError':
					return 'Contesto non sicuro: la fotocamera richiede HTTPS o localhost. Carica un’immagine.';
				default:
					return e.name;
			}
		}

		return e instanceof Error ? e.message : 'errore sconosciuto';
	}

	async function startCamera() {
		stopCamera();
		cameraError = '';
		phase = 'capturing';

		if (!navigator.mediaDevices?.getUserMedia) {
			cameraError =
				'Questo browser non espone la fotocamera (serve HTTPS o localhost). Carica un’immagine dal dispositivo.';
			phase = 'idle';
			return;
		}

		try {
			stream = await navigator.mediaDevices.getUserMedia({
				video: { facingMode: { ideal: facingMode } },
				audio: false
			});
		} catch (e) {
			cameraError = describeCameraError(e);
		}

		phase = 'idle';
	}

	async function switchCamera() {
		facingMode = facingMode === 'environment' ? 'user' : 'environment';
		await startCamera();
	}

	function retryCamera() {
		void startCamera();
	}

	function captureFrame() {
		const video = videoEl;

		if (!video || video.videoWidth === 0 || video.videoHeight === 0) {
			cameraError = 'La fotocamera non ha ancora prodotto un frame: attendi un istante e riprova.';
			return;
		}

		const longest = Math.max(video.videoWidth, video.videoHeight);
		const scale = longest > MAX_CAPTURE_DIMENSION ? MAX_CAPTURE_DIMENSION / longest : 1;
		const width = Math.max(1, Math.round(video.videoWidth * scale));
		const height = Math.max(1, Math.round(video.videoHeight * scale));

		const canvas = document.createElement('canvas');
		canvas.width = width;
		canvas.height = height;

		const ctx = canvas.getContext('2d');
		if (!ctx) {
			cameraError = 'Impossibile leggere il frame dalla fotocamera. Carica un’immagine.';
			return;
		}

		ctx.drawImage(video, 0, 0, width, height);

		canvas.toBlob(
			(blob) => {
				if (!blob) {
					cameraError = 'Conversione dello scatto fallita: riprova o carica un’immagine.';
					return;
				}

				setPreview(blob);
			},
			'image/jpeg',
			CAPTURE_QUALITY
		);
	}

	function onFileSelected(event: Event) {
		const input = event.currentTarget as HTMLInputElement;
		const file = input.files?.[0];

		// Reset so the same file can be picked again after an error.
		input.value = '';
		if (!file) return;

		if (!file.type.startsWith('image/')) {
			cameraError = 'Il file selezionato non è un’immagine.';
			return;
		}

		if (file.size > MAX_UPLOAD_BYTES) {
			cameraError = 'Il file supera i 10 MB: scegli un’immagine più piccola.';
			return;
		}

		cameraError = '';
		setPreview(file);
	}

	// --- Preview -----------------------------------------------------------

	function setPreview(blob: Blob) {
		revokePreview();
		previewBlob = blob;
		previewUrl = URL.createObjectURL(blob);
		tags = [];
		uploadError = '';
		threshold = 0;
		phase = 'ready';
	}

	function revokePreview() {
		if (previewUrl) {
			URL.revokeObjectURL(previewUrl);
		}

		previewUrl = '';
	}

	function retake() {
		revokePreview();
		previewBlob = undefined;
		tags = [];
		uploadError = '';
		threshold = 0;
		phase = 'idle';

		// Re-acquire the camera only if it was never attempted or is still
		// live: after an explicit denial we don't want to re-prompt on every
		// retake, the error message explains what to do.
		if (!stream && !cameraError) {
			void startCamera();
		}
	}

	// --- Upload ------------------------------------------------------------

	async function analyze() {
		if (!previewBlob || phase === 'uploading') return;

		phase = 'uploading';
		uploadError = '';

		const controller = new AbortController();
		const timer = setTimeout(() => controller.abort(), UPLOAD_TIMEOUT_MS);

		try {
			const extension =
				previewBlob.type === 'image/png'
					? 'png'
					: previewBlob.type === 'image/webp'
						? 'webp'
						: 'jpg';

			const form = new FormData();
			form.append('image', previewBlob, `scatto.${extension}`);
			form.append('mode', mode);
			// Deliberately no `threshold`: the slider filters locally, so the
			// server must return everything it has.
			form.append('top_k', String(REQUESTED_TOP_K));

			const res = await fetch('/api/tag', {
				method: 'POST',
				body: form,
				signal: controller.signal
			});

			if (!res.ok) {
				uploadError = await describeUploadError(res);
				phase = 'error';
				return;
			}

			const payload = (await res.json()) as { tags?: Tag[] };

			tags = Array.isArray(payload.tags)
				? payload.tags.filter(
						(tag) => typeof tag?.tag === 'string' && Number.isFinite(tag?.score)
					)
				: [];
			phase = 'success';
		} catch (e) {
			uploadError =
				e instanceof DOMException && e.name === 'AbortError'
					? `Il servizio non ha risposto entro ${UPLOAD_TIMEOUT_MS / 1000} secondi. Riprova.`
					: 'Impossibile contattare il servizio di tagging. Controlla la connessione e riprova.';
			phase = 'error';
		} finally {
			clearTimeout(timer);
		}
	}

	async function describeUploadError(res: Response): Promise<string> {
		// FastAPI returns { "detail": "..." } for HTTPException.
		let detail = '';
		try {
			const body = (await res.json()) as { detail?: unknown };
			if (typeof body.detail === 'string') detail = body.detail;
		} catch {
			// Non-JSON body: the status code alone drives the message.
		}

		switch (res.status) {
			case 400:
				return `Immagine rifiutata dal servizio${detail ? `: ${detail}` : ''}. Prova con un altro scatto.`;
			case 413:
				return 'Immagine troppo grande: scegli un file sotto i 10 MB.';
			case 422:
				return 'Parametri non validi per il servizio di tagging. Riprova.';
			case 429:
				return 'Quota del servizio esaurita: riprova tra qualche minuto.';
			case 502:
				return 'Il fornitore di tagging ha restituito una risposta non valida. Riprova.';
			case 503:
				return 'Servizio di tagging non disponibile in questo momento. Riprova tra poco.';
			default:
				return `Errore imprevisto del servizio (HTTP ${res.status})${detail ? `: ${detail}` : ''}.`;
		}
	}

	// --- Lifecycle ---------------------------------------------------------

	onMount(() => {
		void startCamera();
	});

	onDestroy(() => {
		stopCamera();
		revokePreview();
	});
</script>

<svelte:head><title>Tag · VideoApp</title></svelte:head>

<div class="mx-auto">
	<h1 class="text-2xl font-semibold">Tag</h1>
	<p class="mt-2 text-sm text-gray-600">
		Scatta una foto o caricala dal dispositivo: il servizio restituisce i tag più
		rappresentativi dell’immagine, ordinati per rilevanza.
	</p>

	{#if !data.reachable}
		<p
			class="mt-4 rounded-md border border-yellow-200 bg-yellow-50 px-3 py-2 text-sm text-yellow-800"
		>
			Il servizio di tagging non risponde: verifica che il backend (<code>tagger/</code>) sia
			avviato e raggiungibile.
		</p>
	{:else if !data.credentialsOk}
		<p
			class="mt-4 rounded-md border border-yellow-200 bg-yellow-50 px-3 py-2 text-sm text-yellow-800"
		>
			Il servizio risponde, ma le credenziali Google non risultano configurate: le richieste di
			tagging falliranno finché non vengono impostate.
		</p>
	{/if}

	<div class="mt-6 grid items-start gap-6 lg:grid-cols-2">
		<section class="space-y-4">
			{#if previewUrl}
				<img
					src={previewUrl}
					alt="Anteprima dello scatto"
					class="max-h-80 w-full rounded-lg border border-gray-200 bg-gray-100 object-contain"
				/>

				<div class="flex flex-wrap gap-2">
					<button
						type="button"
						onclick={retake}
						disabled={phase === 'uploading'}
						class="rounded-md border border-gray-300 px-3 py-2 text-sm font-medium hover:bg-gray-100 disabled:opacity-50"
					>
						Ripeti
					</button>
					<button
						type="button"
						onclick={analyze}
						disabled={phase === 'uploading'}
						class="rounded-md bg-gray-900 px-3 py-2 text-sm font-medium text-white hover:bg-gray-700 disabled:opacity-50"
					>
						{phase === 'uploading' ? 'Analisi in corso…' : 'Analizza'}
					</button>
				</div>

				{#if data.objectsEnabled}
					<label class="flex items-center gap-2 text-sm text-gray-700">
						<input type="checkbox" bind:checked={detailed} class="rounded" />
						Analisi dettagliata (aggiunge il riconoscimento degli oggetti)
					</label>
				{/if}
			{:else}
				<div class="relative overflow-hidden rounded-lg border border-gray-200 bg-gray-900">
					<video
						bind:this={videoEl}
						use:attachStream={stream}
						autoplay
						playsinline
						muted
						class="aspect-video w-full object-cover {facingMode === 'user'
							? '-scale-x-100'
							: ''} {stream ? '' : 'invisible'}"
					></video>

					{#if !stream}
						<p
							class="absolute inset-0 flex items-center justify-center px-4 text-center text-sm text-gray-300"
						>
							{cameraError
								? 'Fotocamera non disponibile'
								: phase === 'capturing'
									? 'Richiesta accesso alla fotocamera…'
									: 'Fotocamera non avviata'}
						</p>
					{/if}
				</div>

				{#if cameraError}
					<p
						role="alert"
						class="rounded-md border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700"
					>
						{cameraError}
					</p>
				{/if}

				<div class="flex flex-wrap gap-2">
					<button
						type="button"
						onclick={captureFrame}
						disabled={!stream}
						class="rounded-md bg-gray-900 px-3 py-2 text-sm font-medium text-white hover:bg-gray-700 disabled:opacity-50"
					>
						Scatta
					</button>
					<button
						type="button"
						onclick={switchCamera}
						disabled={!stream}
						class="rounded-md border border-gray-300 px-3 py-2 text-sm font-medium hover:bg-gray-100 disabled:opacity-50"
					>
						Cambia fotocamera
					</button>
					{#if !stream}
						<button
							type="button"
							onclick={retryCamera}
							class="rounded-md border border-gray-300 px-3 py-2 text-sm font-medium hover:bg-gray-100"
						>
							Riprova fotocamera
						</button>
					{/if}
				</div>

				<label class="block text-sm font-medium text-gray-700">
					Oppure carica un’immagine
					<input
						type="file"
						accept="image/jpeg,image/png,image/webp"
						onchange={onFileSelected}
						class="mt-1 block w-full text-sm"
					/>
				</label>
			{/if}
		</section>

		<section aria-live="polite" class="space-y-4">
			<h2 class="text-lg font-medium">Risultati</h2>

			{#if phase === 'uploading'}
				<p class="text-sm text-gray-600">Analisi in corso…</p>
			{:else if phase === 'error'}
				<div class="space-y-3 rounded-md border border-red-200 bg-red-50 p-3 text-sm text-red-700">
					<p>{uploadError}</p>
					<button
						type="button"
						onclick={analyze}
						class="rounded-md bg-red-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-red-700"
					>
						Riprova
					</button>
				</div>
			{:else if phase === 'success'}
				{#if tags.length === 0}
					<p class="rounded-md border border-dashed border-gray-300 p-4 text-sm text-gray-500">
						Nessun tag riconosciuto in questa immagine. Prova con uno scatto più vicino al
						soggetto{#if data.objectsEnabled}, oppure attiva l’analisi dettagliata{/if}.
					</p>
				{:else}
					<label class="block text-sm font-medium text-gray-700">
						Soglia minima: {percent(threshold)}%
						<input
							type="range"
							min="0"
							max="1"
							step="0.05"
							bind:value={threshold}
							class="mt-1 w-full"
						/>
					</label>

					{#if visibleTags.length === 0}
						<p class="rounded-md border border-dashed border-gray-300 p-4 text-sm text-gray-500">
							Nessun tag supera la soglia del {percent(threshold)}%: abbassala{#if data.objectsEnabled},
								oppure attiva l’analisi dettagliata e premi «Analizza» di nuovo{/if}.
						</p>
					{:else}
						<ul class="space-y-2">
							{#each visibleTags as tag (tag.tag)}
								<li>
									<div class="flex items-baseline justify-between gap-2 text-sm">
										<span class="font-medium">
											{tag.tag}
											{#if tag.source === 'object'}
												<span
													class="ml-1 rounded bg-gray-100 px-1.5 py-0.5 text-[10px] font-normal text-gray-600"
												>
													oggetto
												</span>
											{/if}
										</span>
										<span class="tabular-nums text-gray-500">{percent(tag.score)}%</span>
									</div>
									<div class="mt-1 h-1.5 overflow-hidden rounded bg-gray-200">
										<div
											class="h-full rounded bg-gray-900"
											style:width={`${percent(tag.score)}%`}
										></div>
									</div>
								</li>
							{/each}
						</ul>
					{/if}
				{/if}
			{:else if phase === 'ready'}
				<p class="text-sm text-gray-600">Scatto pronto: premi «Analizza».</p>
			{:else}
				<p class="text-sm text-gray-500">I risultati appariranno qui dopo l’analisi.</p>
			{/if}
		</section>
	</div>
</div>
