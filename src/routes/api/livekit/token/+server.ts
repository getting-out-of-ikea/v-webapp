import { error, json } from '@sveltejs/kit';
import { AccessToken } from 'livekit-server-sdk';
import { LIVEKIT_API_KEY, LIVEKIT_API_SECRET } from '$env/static/private';
import type { RequestHandler } from './$types';

export const GET: RequestHandler = async ({ locals, url }) => {
	const { user } = await locals.safeGetSession();

	if (!user) {
		error(401, 'Devi effettuare il login per partecipare alla videochiamata.');
	}

	const roomName = url.searchParams.get('room') ?? 'main';

	const at = new AccessToken(LIVEKIT_API_KEY, LIVEKIT_API_SECRET, {
		identity: user.id,
		name: user.email ?? user.id
	});

	at.addGrant({
		room: roomName,
		roomJoin: true,
		canPublish: true,
		canSubscribe: true
	});

	return json({ token: await at.toJwt() });
};
