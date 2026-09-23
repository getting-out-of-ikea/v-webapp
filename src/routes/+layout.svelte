<script lang="ts">
	import './layout.css';
	import favicon from '$lib/assets/favicon.svg';
	import { invalidate } from '$app/navigation';
	import { resolve } from '$app/paths';
	import { onMount } from 'svelte';

	let { data, children } = $props();

	let { supabase, session, user } = $derived(data);

	onMount(() => {
		const {
			data: { subscription }
		} = supabase.auth.onAuthStateChange((_, newSession) => {
			if (newSession?.expires_at !== session?.expires_at) {
				invalidate('supabase:auth');
			}
		});

		return () => subscription.unsubscribe();
	});
</script>

<svelte:head><link rel="icon" href={favicon} /></svelte:head>

<div class="flex min-h-screen flex-col bg-gray-50 text-gray-900">
	<header class="border-b border-gray-200 bg-white">
		<nav class="mx-auto flex max-w-5xl items-center justify-between px-4 py-3">
			<a href={resolve('/')} class="text-lg font-semibold">VideoApp</a>
			<div class="flex items-center gap-4 text-sm">
				{#if user}
					<span class="text-gray-600">{user.email}</span>
					<form method="POST" action={resolve('/logout')}>
						<button
							type="submit"
							class="rounded-md border border-gray-300 px-3 py-1.5 hover:bg-gray-100"
						>
							Esci
						</button>
					</form>
				{:else}
					<a href={resolve('/login')} class="hover:underline">Accedi</a>
					<a
						href={resolve('/register')}
						class="rounded-md bg-gray-900 px-3 py-1.5 text-white hover:bg-gray-700"
					>
						Registrati
					</a>
				{/if}
			</div>
		</nav>
	</header>
	<main class="mx-auto w-full max-w-5xl flex-1 px-4 py-8">
		{@render children()}
	</main>
</div>
