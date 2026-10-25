<script lang="ts">
	let { data } = $props();

	type Task = (typeof data.personalTasks)[number];
</script>

<svelte:head><title>Le mie task · VideoApp</title></svelte:head>

<div class="mx-auto max-w-2xl space-y-8">
	<h1 class="text-2xl font-semibold">Le mie task</h1>

	{#snippet taskList(tasks: Task[], emptyLabel: string)}
		{#if tasks.length === 0}
			<p class="rounded-md border border-dashed border-gray-300 p-4 text-sm text-gray-500">
				{emptyLabel}
			</p>
		{:else}
			<ul class="divide-y divide-gray-200 rounded-md border border-gray-200 bg-white">
				{#each tasks as task (task.id)}
					<li class="flex items-center gap-3 px-4 py-3">
						<form method="POST" action="?/toggle">
							<input type="hidden" name="id" value={task.id} />
							<input type="hidden" name="done" value={String(!task.done)} />
							<button
								type="submit"
								class="text-lg leading-none"
								aria-label={task.done ? 'Segna come da fare' : 'Segna come completata'}
							>
								{task.done ? '✅' : '⬜'}
							</button>
						</form>
						<div class="min-w-0 flex-1">
							<p class={task.done ? 'text-gray-400 line-through' : ''}>{task.title}</p>
							<p class="text-xs text-gray-500">
								Stanza «{task.room_name}» · {new Date(task.created_at).toLocaleString('it-IT')}
							</p>
						</div>
					</li>
				{/each}
			</ul>
		{/if}
	{/snippet}

	<section class="space-y-3">
		<h2 class="text-lg font-medium">Assegnate a me</h2>
		{@render taskList(
			data.personalTasks,
			'Nessuna task personale: fatti taggare con @ durante una call per crearne una.'
		)}
	</section>

	<section class="space-y-3">
		<h2 class="text-lg font-medium">Task di gruppo (@everyone)</h2>
		{@render taskList(data.groupTasks, 'Nessuna task di gruppo al momento.')}
	</section>
</div>
