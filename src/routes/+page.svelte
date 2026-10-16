<script lang="ts">
	import { resolve } from '$app/paths';
	import { onMount } from 'svelte';

	let count = $state<number | null>(null);
	let names = $state<string[]>([]);
	let loading = $state(true);
	let errorMessage = $state<string | null>(null);

	async function refresh() {
		try {
			const res = await fetch('/api/livekit/participants');
			if (!res.ok) {
				throw new Error(await res.text());
			}
			const data = (await res.json()) as { count: number | null; names: string[] };
			count = data.count;
			names = data.names;
			errorMessage = null;
		} catch (e) {
			errorMessage = e instanceof Error ? e.message : 'Impossibile contattare il server.';
		} finally {
			loading = false;
		}
	}

	onMount(() => {
		void refresh();
		const interval = setInterval(refresh, 5000);
		return () => clearInterval(interval);
	});
</script>

<svelte:head><title>Sala d'attesa · VideoApp</title></svelte:head>

<div class="flex min-h-screen items-center justify-center bg-gray-950 p-4 text-white">
	<div class="w-full max-w-md space-y-6 text-center">
		<h1 class="text-3xl font-bold">Sala d'attesa</h1>
		<p class="text-gray-400">Stanza: <span class="font-medium text-white">main</span></p>

		{#if loading}
			<p class="text-sm text-gray-500">Controllo chi c'è dentro…</p>
		{:else if errorMessage}
			<p class="rounded-md bg-red-500/15 p-3 text-sm text-red-300">{errorMessage}</p>
		{:else if count === null}
			<p class="text-sm text-gray-500">
				Impossibile contattare il server video, ma puoi comunque entrare.
			</p>
		{:else}
			<div class="rounded-lg border border-gray-800 bg-gray-900 p-6">
				<p class="text-5xl font-bold tabular-nums">{count}</p>
				<p class="mt-1 text-sm text-gray-400">
					{count === 0 ? 'Nessuno' : count === 1 ? '1 persona' : `${count} persone`} in chiamata
				</p>
				{#if names.length > 0}
					<ul class="mt-4 space-y-1 text-left text-sm text-gray-300">
						{#each names as name}
							<li class="flex items-center gap-2">
								<span class="h-2 w-2 rounded-full bg-green-400"></span>
								{name}
							</li>
						{/each}
					</ul>
				{/if}
			</div>
		{/if}

		<a
			href={resolve('/room')}
			class="block rounded-md bg-blue-600 px-6 py-3 text-lg font-medium transition hover:bg-blue-500"
		>
			Vai alla chiamata
		</a>
		<p class="text-xs text-gray-500">Il conteggio si aggiorna automaticamente ogni 5 secondi.</p>
	</div>
</div>
