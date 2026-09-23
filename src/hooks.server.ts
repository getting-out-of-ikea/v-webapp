import { redirect, type Handle } from '@sveltejs/kit';
import { sequence } from '@sveltejs/kit/hooks';
import { createSupabaseServerClient } from '$lib/supabase/server';

const supabase: Handle = async ({ event, resolve }) => {
	event.locals.supabase = createSupabaseServerClient(event);

	/**
	 * A differenza di `supabase.auth.getSession()`, valida il JWT
	 * contattando il server Supabase prima di considerarlo attendibile.
	 */
	event.locals.safeGetSession = async () => {
		const {
			data: { session }
		} = await event.locals.supabase.auth.getSession();

		if (!session) {
			return { session: null, user: null };
		}

		const {
			data: { user },
			error
		} = await event.locals.supabase.auth.getUser();

		if (error) {
			return { session: null, user: null };
		}

		return { session, user };
	};

	return resolve(event, {
		filterSerializedResponseHeaders(name) {
			return name === 'content-range' || name === 'x-supabase-api-version';
		}
	});
};

const publicPaths = ['/login', '/register'];

function isPublic(pathname: string): boolean {
	return publicPaths.includes(pathname) || pathname.startsWith('/demo');
}

const authGuard: Handle = async ({ event, resolve }) => {
	const { session, user } = await event.locals.safeGetSession();
	event.locals.session = session;
	event.locals.user = user;

	// `event.route.id` è null per asset statici (/_app/*), che restano pubblici
	if (!session && event.route.id && !isPublic(event.url.pathname)) {
		redirect(303, '/login');
	}

	if (session && publicPaths.includes(event.url.pathname)) {
		redirect(303, '/room');
	}

	return resolve(event);
};

export const handle: Handle = sequence(supabase, authGuard);
