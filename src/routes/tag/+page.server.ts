import { TAGGER_URL } from '$lib/tagger';
import type { PageServerLoad } from './$types';

interface Health {
	status: string;
	credentials_ok: boolean;
	project: string | null;
	features: string[];
}

// Short probe, not part of the page's critical path.
const HEALTH_TIMEOUT_MS = 1500;

export const load: PageServerLoad = async ({ fetch }) => {
	// `/health` is best-effort: if the tagger is down the page must still open
	// and explain the problem instead of failing the whole navigation.
	const controller = new AbortController();
	const timer = setTimeout(() => controller.abort(), HEALTH_TIMEOUT_MS);

	try {
		const res = await fetch(`${TAGGER_URL}/health`, { signal: controller.signal });

		if (!res.ok) {
			throw new Error(`tagger /health responded ${res.status}`);
		}

		const health = (await res.json()) as Health;
		const features = Array.isArray(health.features) ? health.features : [];

		return {
			reachable: true,
			credentialsOk: health.credentials_ok === true,
			// The "detailed" toggle is only meaningful when the backend exposes
			// object localization; otherwise the UI hides it and asks for
			// `mode=labels`.
			objectsEnabled: features.includes('objects')
		};
	} catch {
		return {
			reachable: false,
			credentialsOk: false,
			objectsEnabled: false
		};
	} finally {
		clearTimeout(timer);
	}
};
