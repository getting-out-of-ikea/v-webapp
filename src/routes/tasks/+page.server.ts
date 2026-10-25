import { error } from '@sveltejs/kit';
import type { Actions, PageServerLoad } from './$types';

export const load: PageServerLoad = async ({ locals }) => {
	const { user } = await locals.safeGetSession();

	if (!user) {
		error(401, 'Devi effettuare il login per vedere le tue task.');
	}

	const { data, error: dbError } = await locals.supabase
		.from('tasks')
		.select('id, title, room_name, done, created_at, assignee_id')
		.or(`assignee_id.eq.${user.id},assignee_id.is.null`)
		.order('created_at', { ascending: false });

	if (dbError) {
		error(500, `Impossibile caricare le task: ${dbError.message}`);
	}

	const tasks = data ?? [];

	return {
		personalTasks: tasks.filter((t) => t.assignee_id === user.id),
		groupTasks: tasks.filter((t) => t.assignee_id === null)
	};
};

export const actions: Actions = {
	toggle: async ({ locals, request }) => {
		const { user } = await locals.safeGetSession();

		if (!user) {
			error(401, 'Devi effettuare il login.');
		}

		const form = await request.formData();
		const id = String(form.get('id') ?? '');
		const done = form.get('done') === 'true';

		const { error: dbError } = await locals.supabase.from('tasks').update({ done }).eq('id', id);

		if (dbError) {
			error(500, `Impossibile aggiornare la task: ${dbError.message}`);
		}
	}
};
