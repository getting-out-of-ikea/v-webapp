import { fail, redirect } from '@sveltejs/kit';
import type { Actions } from './$types';

export const actions: Actions = {
	default: async ({ request, locals: { supabase } }) => {
		const formData = await request.formData();
		const email = formData.get('email')?.toString() ?? '';
		const password = formData.get('password')?.toString() ?? '';

		if (!email || !password) {
			return fail(400, { error: 'Email e password sono obbligatorie.', email, message: '' });
		}

		if (password.length < 6) {
			return fail(400, {
				error: 'La password deve contenere almeno 6 caratteri.',
				email,
				message: ''
			});
		}

		const { data, error } = await supabase.auth.signUp({ email, password });

		if (error) {
			return fail(400, { error: error.message, email, message: '' });
		}

		// Se su Supabase è attiva la conferma email, la sessione non esiste ancora
		if (!data.session) {
			return {
				error: '',
				email,
				message: 'Registrazione completata! Controlla la tua email per confermare l’account.'
			};
		}

		redirect(303, '/room');
	}
};
