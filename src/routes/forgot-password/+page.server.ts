import { fail } from '@sveltejs/kit';
import type { Actions } from './$types';

export const actions: Actions = {
	default: async ({ locals, request, url }) => {
		const form = await request.formData();
		const email = String(form.get('email') ?? '').trim();

		if (!email) {
			return fail(400, { ok: false, message: 'Inserisci il tuo indirizzo email.' });
		}

		const { error: resetError } = await locals.supabase.auth.resetPasswordForEmail(email, {
			redirectTo: `${url.origin}/reset-password`
		});

		if (resetError) {
			return fail(500, {
				ok: false,
				message: `Impossibile inviare l'email di recupero: ${resetError.message}`
			});
		}

		return { ok: true, message: '' };
	}
};
