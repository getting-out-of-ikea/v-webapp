import { error, json } from '@sveltejs/kit';
import { RoomServiceClient } from 'livekit-server-sdk';
import { env } from '$env/dynamic/public';
import { LIVEKIT_API_KEY, LIVEKIT_API_SECRET } from '$env/static/private';
import type { RequestHandler } from './$types';

export const GET: RequestHandler = async ({ locals }) => {
	const { user } = await locals.safeGetSession();

	if (!user) {
		error(401, 'Devi effettuare il login.');
	}

	const serverUrl = env.PUBLIC_LIVEKIT_URL;

	if (!serverUrl) {
		error(500, 'PUBLIC_LIVEKIT_URL non configurata.');
	}

	// RoomServiceClient vuole http(s): LiveKit espone la sua API HTTP sulla stessa porta
	const httpUrl = serverUrl.replace(/^ws(s?):\/\//, 'http$1://');

	try {
		const svc = new RoomServiceClient(httpUrl, LIVEKIT_API_KEY, LIVEKIT_API_SECRET);
		const participants = await svc.listParticipants('main');

		return json({
			count: participants.length,
			names: participants
				.map((p) => p.name || p.identity)
				.filter(Boolean)
				.slice(0, 10)
		});
	} catch (e) {
		console.error('Impossibile contare i partecipanti LiveKit:', e);
		// Non bloccare la sala d'attesa se LiveKit è irraggiungibile: mostriamo un placeholder
		return json({ count: null, names: [] });
	}
};
