<script lang="ts">
	import './layout.css';
	import favicon from '$lib/assets/favicon.svg';
	import { goto, invalidate } from '$app/navigation';
	import { resolve } from '$app/paths';
	import { onMount } from 'svelte';

	let { data, children } = $props();

	let { supabase, session, user } = $derived(data);

	const menuItems = [
		{
			href: '/room',
			label: 'Videocall',
			icon: `M15.75 10.5l4.72-4.72a.75.75 0 011.28.53v11.38a.75.75 0 01-1.28.53l-4.72-4.72M4.5 18.75h9a2.25 2.25 0 002.25-2.25v-9A2.25 2.25 0 0013.5 5.25h-9A2.25 2.25 0 002.25 7.5v9a2.25 2.25 0 002.25 2.25z`
		},
		{
			href: '/bot/chatbot',
			label: 'Chatbot',
			icon: `M2.25 12.76c0 1.6 1.123 2.994 2.707 3.227 1.087.16 2.185.283 3.293.369V21l4.076-4.076a1.526 1.526 0 011.037-.443 48.282 48.282 0 005.68-.494c1.584-.233 2.707-1.626 2.707-3.228V6.741c0-1.602-1.123-2.995-2.707-3.228A48.394 48.394 0 0012 3c-2.392 0-4.744.175-7.043.513C3.373 3.746 2.25 5.14 2.25 6.741v6.018z`
		},
		{
			href: '/tag',
			label: 'Tag',
			icon: `M9.568 3H5.25A2.25 2.25 0 003 5.25v4.318c0 .597.237 1.17.659 1.591l9.581 9.581c.699.699 1.78.872 2.607.33a18.095 18.095 0 005.223-5.223c.542-.827.369-1.908-.33-2.607L11.16 3.66A2.25 2.25 0 009.568 3zM6 6h.008v.008H6V6z`
		},
		{
			href: '/tasks',
			label: 'Tasks',
			icon: `M8.25 7.5V6.108c0-1.135.845-2.098 1.976-2.192.373-.03.748-.057 1.123-.08M15.75 18H18a2.25 2.25 0 002.25-2.25V6.108c0-1.135-.845-2.098-1.976-2.192a48.424 48.424 0 00-1.123-.08M15.75 18.75v-1.875a3.375 3.375 0 00-3.375-3.375h-1.5a1.125 1.125 0 01-1.125-1.125v-1.5A3.375 3.375 0 006.375 7.5H5.25m11.9-3.664A2.251 2.251 0 0015 2.25h-1.5a2.251 2.251 0 00-2.15 1.586m5.8 0c.065.21.1.433.1.664v.75h-6V4.5c0-.231.035-.454.1-.664M6.75 7.5H4.875c-.621 0-1.125.504-1.125 1.125v12c0 .621.504 1.125 1.125 1.125h9.75c.621 0 1.125-.504 1.125-1.125V16.5a9 9 0 00-9-9z`
		}
	];

	let showRoomPopup = $state(false);
	let roomName = $state('');
	let roomPopupMessage = $state('');

	function openRoomPopup() {
		showRoomPopup = true;
		roomName = '';
		roomPopupMessage = '';
	}

	function closeRoomPopup() {
		showRoomPopup = false;
		roomName = '';
		roomPopupMessage = '';
	}

	function submitRoomPopup() {
		const trimmed = roomName.trim();
		if (!trimmed) {
			roomPopupMessage = 'Inserisci un nome per la stanza.';
			return;
		}

		void goto(`/room?room=${encodeURIComponent(trimmed)}`);
		closeRoomPopup();
	}

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
			<div class="flex items-center gap-8">
				<a href={resolve('/')} class="text-lg font-semibold">
					Big App v. {__APP_VERSION__}
					<span class="ml-1 text-xs font-normal text-gray-500">({__APP_BUILD__})</span>
				</a>
				{#if user}
					<div class="relative flex items-center gap-6" aria-label="Menu principale">
						{#each menuItems as item (item.href)}
							<a
								href={resolve(item.href)}
								class="group flex flex-col items-center gap-1"
								onclick={(e) => {
									if (item.href === '/room') {
										e.preventDefault();
										openRoomPopup();
									}
								}}
							>
								<svg
									xmlns="http://www.w3.org/2000/svg"
									fill="none"
									viewBox="0 0 24 24"
									stroke-width="1.5"
									stroke="currentColor"
									class="h-6 w-6 text-gray-700 group-hover:text-gray-900"
								>
									<path stroke-linecap="round" stroke-linejoin="round" d={item.icon}></path>
								</svg>
								<span class="text-[11px] font-medium text-gray-600 group-hover:text-gray-900">
									{item.label}
								</span>
							</a>
						{/each}

						{#if showRoomPopup}
							<div
								class="absolute left-0 top-full mt-2 w-72 rounded-lg border border-gray-200 bg-white p-4 shadow-lg"
							>
								<label class="block text-sm font-medium text-gray-700">
									Nome della stanza
								</label>
								<input
									type="text"
									bind:value={roomName}
									placeholder="es. riunione"
									class="mt-1 w-full rounded-md"
								/>
								{#if roomPopupMessage}
									<p class="mt-2 text-sm text-red-600">{roomPopupMessage}</p>
								{/if}
								<div class="mt-4 flex justify-end gap-2">
									<button
										type="button"
										class="rounded-md border border-gray-300 px-3 py-1.5 text-sm hover:bg-gray-100"
										onclick={closeRoomPopup}
									>
										Annulla
									</button>
									<button
										type="button"
										class="rounded-md bg-gray-900 px-3 py-1.5 text-sm text-white hover:bg-gray-700"
										onclick={submitRoomPopup}
									>
										Apri stanza
									</button>
								</div>
							</div>
						{/if}
					</div>
				{/if}
			</div>
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
