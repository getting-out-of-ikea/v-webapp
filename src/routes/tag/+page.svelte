<script lang="ts">
	import { onDestroy } from 'svelte';
	import { PUBLIC_TAGGER_URL } from '$env/static/public';

	type Tag = { tag: string; score: number; source: 'label' | 'object' };
	type TagResponse = {
		provider: string;
		features: string[];
		tags: Tag[];
		timing_ms: { preprocess: number; upstream: number; scoring: number };
	};

	type State = 'idle' | 'capturing' | 'ready' | 'uploading' | 'success' | 'error';

	const TAGGER_URL = PUBLIC_TAGGER_URL || 'http://localhost:8000';
	const MAX_DIMENSION = 1024;
	const JPEG_QUALITY = 0.85;
	const UPLOAD_TIMEOUT_MS = 20_000;

	let state = $state<State>('idle');
	let errorMessage = $state<string | null>(null);
	let tags = $state<Tag[]>([]);
	let features = $state<string[]>([]);
	let timing = $state<TagResponse['timing_ms'] | null>(null);
	let threshold = $state(0);
	let detailed = $state(false);
	let facingMode = $state<'environment' | 'user'>('environment');
	let cameraError = $state<string | null>(null);

	let videoEl = $state<HTMLVideoElement | null>(null);
	let canvasEl = $state<HTMLCanvasElement | null>(null);
	let previewUrl = $state<string | null>(null);
	let blob = $state<Blob | null>(null);
	let stream: MediaStream | null = null;

	const filteredTags = $derived(tags.filter((t) => t.score >= threshold));

	function stopStream() {
		if (stream) {
			stream.getTracks().forEach((t) => t.stop());
			stream = null;
		}
	}

	async function startCamera() {
		cameraError = null;
		stopStream();
		try {
			stream = await navigator.mediaDevices.getUserMedia({
				video: { facingMode },
				audio: false
			});
			if (videoEl) {
				videoEl.srcObject = stream;
				await videoEl.play();
			}
			state = 'capturing';
		} catch (err) {
			cameraError =
				err instanceof Error
					? `Impossibile accedere alla fotocamera: ${err.message}`
					: 'Impossibile accedere alla fotocamera.';
			state = 'idle';
		}
	}

	async function switchCamera() {
		facingMode = facingMode === 'environment' ? 'user' : 'environment';
		if (state === 'capturing') {
			await startCamera();
		}
	}

	function capture() {
		if (!videoEl || !canvasEl) return;
		const vw = videoEl.videoWidth;
		const vh = videoEl.videoHeight;
		if (!vw || !vh) return;

		const scale = Math.min(1, MAX_DIMENSION / Math.max(vw, vh));
		const w = Math.round(vw * scale);
		const h = Math.round(vh * scale);

		canvasEl.width = w;
		canvasEl.height = h;
		const ctx = canvasEl.getContext('2d');
		if (!ctx) return;
		ctx.drawImage(videoEl, 0, 0, w, h);

		canvasEl.toBlob(
			(b) => {
				if (!b) return;
				setBlob(b);
			},
			'image/jpeg',
			JPEG_QUALITY
		);
	}

	function setBlob(b: Blob) {
		if (previewUrl) URL.revokeObjectURL(previewUrl);
		blob = b;
		previewUrl = URL.createObjectURL(b);
		state = 'ready';
		tags = [];
		features = [];
		timing = null;
		errorMessage = null;
		stopStream();
	}

	function onFileChange(e: Event) {
		const input = e.currentTarget as HTMLInputElement;
		const file = input.files?.[0];
		if (!file) return;
		setBlob(file);
		input.value = '';
	}

	function reset() {
		if (previewUrl) URL.revokeObjectURL(previewUrl);
		previewUrl = null;
		blob = null;
		tags = [];
		features = [];
		timing = null;
		errorMessage = null;
		state = 'idle';
	}

	async function analyze() {
		if (!blob) return;
		state = 'uploading';
		errorMessage = null;

		const controller = new AbortController();
		const timeout = setTimeout(() => controller.abort(), UPLOAD_TIMEOUT_MS);

		try {
			const form = new FormData();
			form.append('image', blob, 'photo.jpg');
			form.append('mode', detailed ? 'auto' : 'labels');
			form.append('top_k', '10');
			form.append('threshold', '0');

			const res = await fetch(`${TAGGER_URL}/tag`, {
				method: 'POST',
				body: form,
				signal: controller.signal
			});

			if (!res.ok) {
				const detail = await safeDetail(res);
				throw new Error(detail ?? `Errore ${res.status}`);
			}

			const data = (await res.json()) as TagResponse;
			tags = data.tags;
			features = data.features;
			timing = data.timing_ms;
			state = 'success';
		} catch (err) {
			if (err instanceof DOMException && err.name === 'AbortError') {
				errorMessage = 'Richiesta scaduta. Riprova.';
			} else if (err instanceof TypeError) {
				errorMessage = 'Backend non raggiungibile. Verifica che il servizio tagger sia attivo.';
			} else {
				errorMessage = err instanceof Error ? err.message : 'Errore sconosciuto.';
			}
			state = 'error';
		} finally {
			clearTimeout(timeout);
		}
	}

	async function safeDetail(res: Response): Promise<string | null> {
		try {
			const body = await res.json();
			if (typeof body?.detail === 'string') return body.detail;
		} catch {
			/* ignore */
		}
		if (res.status === 429) return 'Quota del fornitore esaurita. Riprova più tardi.';
		if (res.status === 503) return 'Fornitore non disponibile. Riprova più tardi.';
		return null;
	}

	onDestroy(() => {
		stopStream();
		if (previewUrl) URL.revokeObjectURL(previewUrl);
	});
</script>

<svelte:head><title>Tag immagine</title></svelte:head>

<section class="space-y-6">
	<header class="space-y-1">
		<h1 class="text-2xl font-semibold">Tag automatici</h1>
		<p class="text-sm text-gray-600">
			Scatta una foto o caricane una: il backend restituisce i tag più rilevanti.
		</p>
	</header>

	<div class="grid gap-6 md:grid-cols-2">
		<!-- Camera / preview -->
		<div class="space-y-3">
			{#if state === 'idle' || state === 'capturing'}
				<div class="relative overflow-hidden rounded-lg bg-black">
					<!-- svelte-ignore a11y_media_has_caption -->
					<video
						bind:this={videoEl}
						class="aspect-video w-full object-cover"
						playsinline
						muted
					></video>
					{#if state === 'idle'}
						<div class="absolute inset-0 flex items-center justify-center bg-black/60 text-white">
							<p class="text-sm">Fotocamera non attiva</p>
						</div>
					{/if}
				</div>

				{#if cameraError}
					<p class="text-sm text-red-600" role="alert">{cameraError}</p>
				{/if}

				<div class="flex flex-wrap gap-2">
					{#if state === 'idle'}
						<button
							type="button"
							class="rounded-md bg-gray-900 px-3 py-1.5 text-sm text-white hover:bg-gray-700"
							onclick={startCamera}
						>
							Attiva fotocamera
						</button>
					{:else}
						<button
							type="button"
							class="rounded-md bg-gray-900 px-3 py-1.5 text-sm text-white hover:bg-gray-700"
							onclick={capture}
						>
							Scatta
						</button>
						<button
							type="button"
							class="rounded-md border border-gray-300 px-3 py-1.5 text-sm hover:bg-gray-100"
							onclick={switchCamera}
						>
							Cambia camera
						</button>
					{/if}
					<label
						class="cursor-pointer rounded-md border border-gray-300 px-3 py-1.5 text-sm hover:bg-gray-100"
					>
						Carica file
						<input type="file" accept="image/*" class="hidden" onchange={onFileChange} />
					</label>
				</div>
			{:else if previewUrl}
				<div class="overflow-hidden rounded-lg bg-black">
					<img src={previewUrl} alt="Anteprima dello scatto" class="aspect-video w-full object-contain" />
				</div>
				<div class="flex flex-wrap gap-2">
					<button
						type="button"
						class="rounded-md border border-gray-300 px-3 py-1.5 text-sm hover:bg-gray-100"
						onclick={reset}
						disabled={state === 'uploading'}
					>
						Ripeti
					</button>
					<button
						type="button"
						class="rounded-md bg-gray-900 px-3 py-1.5 text-sm text-white hover:bg-gray-700 disabled:opacity-50"
						onclick={analyze}
						disabled={state === 'uploading'}
					>
						{state === 'uploading' ? 'Analisi…' : 'Analizza'}
					</button>
				</div>
			{/if}

			<canvas bind:this={canvasEl} class="hidden"></canvas>
		</div>

		<!-- Risultati -->
		<div class="space-y-3" aria-live="polite">
			<div class="flex items-center justify-between">
				<h2 class="text-lg font-semibold">Risultati</h2>
				<label class="flex items-center gap-2 text-sm text-gray-700">
					<input type="checkbox" bind:checked={detailed} disabled={state === 'uploading'} />
					Dettagliato
				</label>
			</div>

			{#if state === 'uploading'}
				<p class="text-sm text-gray-600">Analisi in corso…</p>
			{:else if state === 'error' && errorMessage}
				<div class="rounded-md border border-red-200 bg-red-50 p-3 text-sm text-red-700">
					{errorMessage}
				</div>
			{:else if state === 'success'}
				{#if tags.length === 0}
					<p class="text-sm text-gray-600">
						Nessun tag rilevato. Prova con un'altra immagine o attiva la modalità dettagliata.
					</p>
				{:else}
					<div class="space-y-2">
						<label class="block text-sm text-gray-700">
							Soglia minima: {threshold.toFixed(2)}
							<input
								type="range"
								min="0"
								max="1"
								step="0.01"
								bind:value={threshold}
								class="mt-1 w-full"
							/>
						</label>

						{#if filteredTags.length === 0}
							<p class="text-sm text-gray-600">
								Nessun tag supera la soglia. Abbassala per vedere più risultati.
							</p>
						{:else}
							<ul class="space-y-2">
								{#each filteredTags as t (t.tag)}
									<li class="space-y-1">
										<div class="flex items-center justify-between text-sm">
											<span class="font-medium">
												{t.tag}
												{#if t.source === 'object'}
													<span
														class="ml-1 rounded bg-gray-200 px-1.5 py-0.5 text-xs text-gray-700"
														>oggetto</span
													>
												{/if}
											</span>
											<span class="text-gray-500">{t.score.toFixed(2)}</span>
										</div>
										<div class="h-1.5 w-full overflow-hidden rounded bg-gray-200">
											<div
												class="h-full bg-gray-900"
												style={`width: ${Math.round(t.score * 100)}%`}
											></div>
										</div>
									</li>
								{/each}
							</ul>
						{/if}

						{#if timing}
							<p class="pt-2 text-xs text-gray-500">
								Feature: {features.join(', ')} · preprocess {timing.preprocess.toFixed(0)} ms ·
								upstream {timing.upstream.toFixed(0)} ms · scoring {timing.scoring.toFixed(0)} ms
							</p>
						{/if}
					</div>
				{/if}
			{:else}
				<p class="text-sm text-gray-600">
					Scatta o carica un'immagine per vedere i tag.
				</p>
			{/if}
		</div>
	</div>
</section>
