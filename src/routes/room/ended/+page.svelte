<script lang="ts">
	import { goto } from '$app/navigation';
	import { resolve } from '$app/paths';
	import { onDestroy, onMount } from 'svelte';

	const REDIRECT_SECONDS = 5;

	let secondsLeft = $state(REDIRECT_SECONDS);
	let interval: ReturnType<typeof setInterval> | undefined;

	onMount(() => {
		interval = setInterval(() => {
			secondsLeft -= 1;

			if (secondsLeft <= 0) {
				clearInterval(interval);
				void goto(resolve('/'));
			}
		}, 1000);
	});

	onDestroy(() => {
		clearInterval(interval);
	});
</script>

<svelte:head><title>Chiamata conclusa · VideoApp</title></svelte:head>

<div class="flex h-screen flex-col items-center justify-center gap-4 bg-gray-950 text-white">
	<h1 class="text-2xl font-semibold">Chiamata conclusa</h1>
	<p class="text-sm text-gray-400">
		Sarai reindirizzato alla home tra
		<span class="font-semibold text-white">{secondsLeft}</span>
		{secondsLeft === 1 ? 'secondo' : 'secondi'}…
	</p>
	<a href={resolve('/')} class="text-sm font-medium underline">Torna subito alla home</a>
</div>
