import { error, json } from '@sveltejs/kit';
import type { RequestHandler } from './$types';

interface CreateTaskBody {
	room?: string;
	title?: string;
	assignees?: string[] | 'everyone';
}

interface TaskRow {
	created_by: string;
	assignee_id: string | null;
	room_name: string;
	title: string;
}

export const POST: RequestHandler = async ({ locals, request }) => {
	const { user } = await locals.safeGetSession();

	if (!user) {
		error(401, 'Devi effettuare il login per assegnare una task.');
	}

	const body = (await request.json().catch(() => ({}))) as CreateTaskBody;
	const title = body.title?.trim();
	const roomName = body.room?.trim() || 'main';

	if (!title) {
		error(400, 'Il testo della task non può essere vuoto.');
	}

	// @everyone → una singola riga con assignee_id NULL (task di gruppo)
	const rows: TaskRow[] =
		body.assignees === 'everyone'
			? [{ created_by: user.id, assignee_id: null, room_name: roomName, title }]
			: (body.assignees ?? []).map((assigneeId) => ({
					created_by: user.id,
					assignee_id: assigneeId,
					room_name: roomName,
					title
				}));

	if (rows.length === 0) {
		error(400, 'Nessun destinatario valido per la task.');
	}

	const { error: dbError } = await locals.supabase.from('tasks').insert(rows);

	if (dbError) {
		error(500, `Impossibile salvare la task: ${dbError.message}`);
	}

	return json({ created: rows.length }, { status: 201 });
};
