<script lang="ts">
	import { resolve } from '$app/paths';

	let { form } = $props();
</script>

<svelte:head><title>Accedi · VideoApp</title></svelte:head>

<div class="mx-auto max-w-sm">
	<h1 class="mb-6 text-2xl font-semibold">Accedi</h1>

	{#if form?.error}
		<p class="mb-4 rounded-md bg-red-50 p-3 text-sm text-red-700">{form.error}</p>
	{/if}

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
				autocomplete="current-password"
				class="rounded-md"
			/>
		</label>
		<button type="submit" class="rounded-md bg-gray-900 px-4 py-2 text-white hover:bg-gray-700">
			Accedi
		</button>
	</form>

	<p class="mt-4 text-sm text-gray-600">
		Non hai un account?
		<a href={resolve('/register')} class="font-medium underline">Registrati</a>
	</p>
</div>
