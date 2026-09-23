<script lang="ts">
	import { resolve } from '$app/paths';

	let { form } = $props();
</script>

<svelte:head><title>Registrati · VideoApp</title></svelte:head>

<div class="mx-auto max-w-sm">
	<h1 class="mb-6 text-2xl font-semibold">Crea un account</h1>

	{#if form?.error}
		<p class="mb-4 rounded-md bg-red-50 p-3 text-sm text-red-700">{form.error}</p>
	{/if}

	{#if form?.message}
		<p class="mb-4 rounded-md bg-green-50 p-3 text-sm text-green-700">{form.message}</p>
	{:else}
		<form method="POST" class="flex flex-col gap-4">
			<label class="flex flex-col gap-1 text-sm font-medium">
				Email
				<input
					name="email"
					type="email"
					required
					autocomplete="email"
					value={form?.email ?? ''}
					class="rounded-md"
				/>
			</label>
			<label class="flex flex-col gap-1 text-sm font-medium">
				Password
				<input
					name="password"
					type="password"
					required
					minlength="6"
					autocomplete="new-password"
					class="rounded-md"
				/>
			</label>
			<button type="submit" class="rounded-md bg-gray-900 px-4 py-2 text-white hover:bg-gray-700">
				Registrati
			</button>
		</form>
	{/if}

	<p class="mt-4 text-sm text-gray-600">
		Hai già un account?
		<a href={resolve('/login')} class="font-medium underline">Accedi</a>
	</p>
</div>
