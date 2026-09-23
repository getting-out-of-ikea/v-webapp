<script lang="ts">
	import { goto } from '$app/navigation';
	import { resolve } from '$app/paths';
	import { page } from '$app/state';
	import { env } from '$env/dynamic/public';
	import { Room, RoomEvent, Track, type Participant } from 'livekit-client';
	import { onDestroy, onMount } from 'svelte';

	const roomName = $derived(page.url.searchParams.get('room') ?? 'main');

	const room = new Room();

	let connected = $state(false);
	let micEnabled = $state(false);
	let camEnabled = $state(false);
	let sharingScreen = $state(false);
	let errorMessage = $state<string | null>(null);
	let deviceWarning = $state<string | null>(null);

	interface Tile {
		key: string;
		label: string;
		isLocal: boolean;
		isScreenShare: boolean;
		isSpeaking: boolean;
		micMuted: boolean;
		videoTrack: Track | null;
		audioTrack: Track | null;
	}

	let tiles = $state<Tile[]>([]);

	function syncTiles() {
		const all: Participant[] = [room.localParticipant, ...room.remoteParticipants.values()];
		const next: Tile[] = [];

		for (const p of all) {
			const publications = [...p.trackPublications.values()];
			const camera = publications.find((t) => t.source === Track.Source.Camera);
			const screen = publications.find((t) => t.source === Track.Source.ScreenShare);
			const mic = publications.find((t) => t.source === Track.Source.Microphone);
			const displayName = p.name || p.identity || 'Ospite';

			next.push({
				key: `${p.identity}-camera`,
				label: p.isLocal ? `${displayName} (tu)` : displayName,
				isLocal: p.isLocal,
				isScreenShare: false,
				isSpeaking: p.isSpeaking,
				micMuted: mic?.isMuted ?? true,
				videoTrack: camera?.track ?? null,
				audioTrack: p.isLocal ? null : (mic?.track ?? null)
			});

			if (screen?.track) {
				next.push({
					key: `${p.identity}-screen`,
					label: `Schermo di ${displayName}`,
					isLocal: p.isLocal,
					isScreenShare: true,
					isSpeaking: false,
					micMuted: false,
					videoTrack: screen.track,
					audioTrack: null
				});
			}
		}

		tiles = next;
	}

	function attachTrack(node: HTMLMediaElement, track: Track | null) {
		track?.attach(node);

		return {
			update(next: Track | null) {
				if (next !== track) {
					track?.detach(node);
					track = next;
					track?.attach(node);
				}
			},
			destroy() {
				track?.detach(node);
			}
		};
	}

	function describeDeviceError(e: unknown): string {
		if (e instanceof DOMException) {
			switch (e.name) {
				case 'NotFoundError':
				case 'DevicesNotFoundError':
					return 'dispositivo non trovato';
				case 'NotAllowedError':
				case 'PermissionDeniedError':
					return 'permesso negato dal browser';
				case 'NotReadableError':
				case 'TrackStartError':
					return 'dispositivo occupato da un’altra applicazione';
				case 'OverconstrainedError':
					return 'vincoli non supportati dal dispositivo';
				case 'SecurityError':
					return 'contesto non sicuro: servono HTTPS o localhost';
				default:
					return e.name;
			}
		}

		return e instanceof Error ? e.message : 'errore sconosciuto';
	}

	// Restituisce true se il browser rileva almeno una webcam sul sistema
	async function hasVideoInput(): Promise<boolean> {
		try {
			const devices = await navigator.mediaDevices.enumerateDevices();
			return devices.some((d) => d.kind === 'videoinput');
		} catch {
			return true;
		}
	}

	async function handleDisconnect() {
		await goto(resolve('/room/ended'));
	}

	onMount(async () => {
		try {
			const res = await fetch(`/api/livekit/token?room=${encodeURIComponent(roomName)}`);

			if (!res.ok) {
				throw new Error(`Impossibile ottenere il token di accesso (errore ${res.status}).`);
			}

			const { token } = (await res.json()) as { token: string };
			const serverUrl = env.PUBLIC_LIVEKIT_URL;

			if (!serverUrl) {
				throw new Error(
					'PUBLIC_LIVEKIT_URL non configurata: crea il file webapp/.env partendo da .env.example.'
				);
			}

			room
				.on(RoomEvent.TrackSubscribed, syncTiles)
				.on(RoomEvent.TrackUnsubscribed, syncTiles)
				.on(RoomEvent.TrackMuted, syncTiles)
				.on(RoomEvent.TrackUnmuted, syncTiles)
				.on(RoomEvent.ParticipantConnected, syncTiles)
				.on(RoomEvent.ParticipantDisconnected, syncTiles)
				.on(RoomEvent.ActiveSpeakersChanged, syncTiles)
				.on(RoomEvent.LocalTrackPublished, (publication) => {
					if (publication.source === Track.Source.ScreenShare) {
						sharingScreen = true;
					}
					syncTiles();
				})
				.on(RoomEvent.LocalTrackUnpublished, (publication) => {
					if (publication.source === Track.Source.ScreenShare) {
						sharingScreen = false;
					}
					syncTiles();
				})
				.on(RoomEvent.Disconnected, () => void handleDisconnect());

			await room.connect(serverUrl, token);

			// Entriamo comunque nella stanza: camera e microfono si attivano
			// solo se il dispositivo esiste e il browser concede il permesso
			try {
				await room.localParticipant.enableCameraAndMicrophone();
			} catch {
				let micError: string | null = null;
				let camError: string | null = null;

				try {
					await room.localParticipant.setMicrophoneEnabled(true);
				} catch (e) {
					micError = describeDeviceError(e);
					console.warn('Microfono non disponibile:', e);
				}

				try {
					await room.localParticipant.setCameraEnabled(true);
				} catch (e) {
					camError = describeDeviceError(e);
					console.warn('Webcam non disponibile:', e);

					if (!(await hasVideoInput())) {
						camError += ' — il browser non rileva alcuna webcam sul sistema';
					}
				}

				if (micError && camError) {
					deviceWarning = `Microfono e webcam non disponibili (mic: ${micError}; cam: ${camError}): gli altri partecipanti non ti vedranno né ti sentiranno.`;
				} else if (micError) {
					deviceWarning = `Microfono non disponibile (${micError}): gli altri partecipanti non ti sentiranno.`;
				} else if (camError) {
					deviceWarning = `Webcam non disponibile (${camError}): gli altri partecipanti non ti vedranno.`;
				}
			}

			micEnabled = room.localParticipant.isMicrophoneEnabled;
			camEnabled = room.localParticipant.isCameraEnabled;
			connected = true;
			syncTiles();
		} catch (e) {
			errorMessage = e instanceof Error ? e.message : 'Si è verificato un errore imprevisto.';
		}
	});

	onDestroy(() => {
		room.removeAllListeners();
		room.disconnect();
	});

	async function toggleMic() {
		try {
			await room.localParticipant.setMicrophoneEnabled(!micEnabled);
		} catch (e) {
			deviceWarning = `Microfono non disponibile: ${describeDeviceError(e)}.`;
		}
		micEnabled = room.localParticipant.isMicrophoneEnabled;
	}

	async function toggleCam() {
		try {
			await room.localParticipant.setCameraEnabled(!camEnabled);
		} catch (e) {
			deviceWarning = `Webcam non disponibile: ${describeDeviceError(e)}.`;
		}
		camEnabled = room.localParticipant.isCameraEnabled;
	}

	async function toggleScreenShare() {
		try {
			await room.localParticipant.setScreenShareEnabled(!sharingScreen);
		} catch (e) {
			deviceWarning = `Condivisione schermo non disponibile: ${describeDeviceError(e)}.`;
		}
	}
</script>

<svelte:head><title>Videochiamata · VideoApp</title></svelte:head>

{#if errorMessage}
	<div class="mx-auto flex h-screen max-w-sm flex-col items-center justify-center gap-4">
		<p class="w-full rounded-md bg-red-50 p-3 text-sm text-red-700">{errorMessage}</p>
		<a href={resolve('/')} class="text-sm font-medium underline">Torna alla home</a>
	</div>
{:else if !connected}
	<div class="flex h-screen items-center justify-center">
		<p class="text-sm text-gray-600">Connessione alla stanza «{roomName}» in corso…</p>
	</div>
{:else}
	<div class="flex h-screen flex-col bg-gray-950 text-white">
		<header class="flex items-center justify-between px-4 py-3">
			<h1 class="text-sm font-medium">Stanza: {roomName}</h1>
			<span class="text-xs text-gray-400">
				{tiles.filter((t) => !t.isScreenShare).length} partecipanti
			</span>
		</header>

		{#if deviceWarning}
			<p class="mx-4 mb-2 rounded-md bg-yellow-500/15 p-3 text-sm text-yellow-300">
				{deviceWarning}
			</p>
		{/if}

		<main
			class="grid flex-1 gap-3 overflow-y-auto px-4 pb-2"
			style="grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));"
		>
			{#each tiles as tile (tile.key)}
				<div
					class="relative aspect-video self-center overflow-hidden rounded-lg bg-gray-900 {tile.isSpeaking
						? 'ring-2 ring-green-400'
						: ''}"
				>
					{#if tile.videoTrack}
						<video
							use:attachTrack={tile.videoTrack}
							autoplay
							playsinline
							muted={tile.isLocal}
							class="h-full w-full object-cover {tile.isLocal && !tile.isScreenShare
								? '-scale-x-100'
								: ''}"
						>
							<track kind="captions" />
						</video>
					{:else}
						<div class="flex h-full w-full items-center justify-center">
							<span
								class="flex h-16 w-16 items-center justify-center rounded-full bg-gray-700 text-xl font-semibold"
							>
								{tile.label.charAt(0).toUpperCase()}
							</span>
						</div>
					{/if}

					{#if tile.audioTrack}
						<audio use:attachTrack={tile.audioTrack} autoplay></audio>
					{/if}

					<div
						class="absolute bottom-2 left-2 flex items-center gap-1 rounded bg-black/60 px-2 py-1 text-xs"
					>
						{#if tile.micMuted && !tile.isScreenShare}
							<span aria-label="microfono disattivato">🔇</span>
						{/if}
						<span>{tile.label}</span>
					</div>
				</div>
			{/each}
		</main>

		<footer class="flex flex-wrap items-center justify-center gap-3 p-4">
			<button
				onclick={toggleMic}
				class="rounded-full px-4 py-2 text-sm font-medium {micEnabled
					? 'bg-gray-700 hover:bg-gray-600'
					: 'bg-red-600 hover:bg-red-500'}"
			>
				{micEnabled ? 'Disattiva microfono' : 'Attiva microfono'}
			</button>
			<button
				onclick={toggleCam}
				class="rounded-full px-4 py-2 text-sm font-medium {camEnabled
					? 'bg-gray-700 hover:bg-gray-600'
					: 'bg-red-600 hover:bg-red-500'}"
			>
				{camEnabled ? 'Disattiva camera' : 'Attiva camera'}
			</button>
			<button
				onclick={toggleScreenShare}
				class="rounded-full px-4 py-2 text-sm font-medium {sharingScreen
					? 'bg-blue-600 hover:bg-blue-500'
					: 'bg-gray-700 hover:bg-gray-600'}"
			>
				{sharingScreen ? 'Interrompi condivisione' : 'Condividi schermo'}
			</button>
			<button
				onclick={() => room.disconnect()}
				class="rounded-full bg-red-600 px-4 py-2 text-sm font-medium hover:bg-red-500"
			>
				Esci
			</button>
		</footer>
	</div>
{/if}
