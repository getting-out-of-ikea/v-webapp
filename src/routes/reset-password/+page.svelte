<script lang="ts">
	import { enhance } from '$app/forms';
	import { resolve } from '$app/paths';
	import type { ActionData } from './$types';

	let { form }: { form: ActionData } = $props();
</script>

<svelte:head><title>Reimposta password · VideoApp</title></svelte:head>

<div class="flex min-h-screen items-center justify-center bg-gray-50 p-4">
	<div class="w-full max-w-sm space-y-6 rounded-lg bg-white p-8 shadow">
		<div class="space-y-1 text-center">
			<h1 class="text-2xl font-semibold">Reimposta la password</h1>
			<p class="text-sm text-gray-600">Scegli una nuova password per il tuo account.</p>
		</div>

		{#if form?.ok}
			<p class="rounded-md bg-green-50 p-3 text-sm text-green-700">
				Password aggiornata con successo! Ora puoi accedere all'app.
			</p>
			<a
				href={resolve('/')}
				class="block rounded-md bg-blue-600 px-4 py-2 text-center text-sm font-medium text-white hover:bg-blue-500"
			>
				Vai alla home
			</a>
		{:else}
			{#if form && !form.ok}
				<p class="rounded-md bg-red-50 p-3 text-sm text-red-700">{form.message}</p>
			{/if}

			<form method="POST" use:enhance class="space-y-4">
				<label class="block text-sm font-medium text-gray-700">
					Nuova password
					<input
						type="password"
						name="password"
						required
						minlength="6"
						autocomplete="new-password"
						class="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500"
					/>
				</label>
				<label class="block text-sm font-medium text-gray-700">
					Conferma password
					<input
						type="password"
						name="confirm"
						required
						minlength="6"
						autocomplete="new-password"
						class="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500"
					/>
				</label>
				<button
					type="submit"
					class="w-full rounded-md bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-500"
				>
					Aggiorna password
				</button>
			</form>
		{/if}
	</div>
</div>
