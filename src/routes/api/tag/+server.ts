import { TAGGER_URL } from '$lib/tagger';
import { json } from '@sveltejs/kit';
import type { RequestHandler } from './$types';

// The browser gives up after 20 s; leave the proxy a little more room so the
// client sees the backend's real answer (or its timeout) instead of a race.
const PROXY_TIMEOUT_MS = 25_000;

export const POST: RequestHandler = async ({ locals, request }) => {
	const { user } = await locals.safeGetSession();

	if (!user) {
		return json({ detail: 'Devi effettuare il login.' }, { status: 401 });
	}

	const contentType = request.headers.get('content-type') ?? '';

	if (!contentType.startsWith('multipart/form-data')) {
		return json({ detail: 'Richiesta non valida: serve multipart/form-data.' }, { status: 400 });
	}

	// Forward the raw body: re-encoding a FormData would lose the boundary and
	// force a full parse/copy of the image in memory.
	const body = await request.arrayBuffer();

	const controller = new AbortController();
	const timer = setTimeout(() => controller.abort(), PROXY_TIMEOUT_MS);

	let upstream: Response;
	try {
		upstream = await fetch(`${TAGGER_URL}/tag`, {
			method: 'POST',
			headers: { 'content-type': contentType },
			body,
			signal: controller.signal
		});
	} catch {
		return json({ detail: 'Il servizio di tagging non è raggiungibile.' }, { status: 503 });
	} finally {
		clearTimeout(timer);
	}

	const text = await upstream.text();

	return new Response(text, {
		status: upstream.status,
		headers: { 'content-type': upstream.headers.get('content-type') ?? 'application/json' }
	});
};
