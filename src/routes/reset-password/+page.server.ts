import { error, fail } from '@sveltejs/kit';
import type { Actions, PageServerLoad } from './$types';

export const load: PageServerLoad = async ({ locals, url }) => {
	// Il link nell'email di Supabase riporta qui con ?code=... (flusso PKCE):
	// lo scambiamo per una sessione di recupero prima di mostrare il form
	const code = url.searchParams.get('code');

	if (code) {
		const { error: exchangeError } = await locals.supabase.auth.exchangeCodeForSession(code);

		if (exchangeError) {
			error(400, `Link di recupero non valido o scaduto: ${exchangeError.message}`);
		}
	}

	const { session } = await locals.safeGetSession();

	if (!session) {
		error(400, 'Link di recupero non valido o scaduto: richiedi una nuova email di recupero.');
	}
};

export const actions: Actions = {
	default: async ({ locals, request }) => {
		const form = await request.formData();
		const password = String(form.get('password') ?? '');
		const confirm = String(form.get('confirm') ?? '');

		if (password.length < 6) {
			return fail(400, { ok: false, message: 'La password deve contenere almeno 6 caratteri.' });
		}

		if (password !== confirm) {
			return fail(400, { ok: false, message: 'Le password non coincidono.' });
		}

		const { error: updateError } = await locals.supabase.auth.updateUser({ password });

		if (updateError) {
			return fail(400, {
				ok: false,
				message: `Impossibile aggiornare la password: ${updateError.message}`
			});
		}

		return { ok: true, message: '' };
	}
};
