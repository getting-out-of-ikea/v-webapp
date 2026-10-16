<script lang="ts">
	import { enhance } from '$app/forms';
	import { resolve } from '$app/paths';
	import type { ActionData } from './$types';

	let { form }: { form: ActionData } = $props();
</script>

<svelte:head><title>Password dimenticata · VideoApp</title></svelte:head>

<div class="flex min-h-screen items-center justify-center bg-gray-50 p-4">
	<div class="w-full max-w-sm space-y-6 rounded-lg bg-white p-8 shadow">
		<div class="space-y-1 text-center">
			<h1 class="text-2xl font-semibold">Password dimenticata</h1>
			<p class="text-sm text-gray-600">
				Inserisci la tua email: ti invieremo un link per reimpostare la password.
			</p>
		</div>

		{#if form?.ok}
			<p class="rounded-md bg-green-50 p-3 text-sm text-green-700">
				Se l'email è registrata, riceverai a breve un link per reimpostare la password.
				Controlla anche la cartella spam.
			</p>
		{:else}
			{#if form && !form.ok}
				<p class="rounded-md bg-red-50 p-3 text-sm text-red-700">{form.message}</p>
			{/if}

			<form method="POST" use:enhance class="space-y-4">
				<label class="block text-sm font-medium text-gray-700">
					Email
					<input
						type="email"
						name="email"
						required
						autocomplete="email"
						class="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500"
					/>
				</label>
				<button
					type="submit"
					class="w-full rounded-md bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-500"
				>
					Invia email di recupero
				</button>
			</form>
		{/if}

		<p class="text-center text-sm">
			<a href={resolve('/login')} class="font-medium text-blue-600 hover:underline">
				Torna al login
			</a>
		</p>
	</div>
</div>
