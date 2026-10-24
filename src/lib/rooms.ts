export function isValidRoomName(name: string): boolean {
	if (!name || typeof name !== 'string') return false;
	if (name.length > 64) return false;

	// Conservative LiveKit-compatible room name:
	// letters, numbers, dash, underscore.
	return /^[a-zA-Z0-9_-]+$/.test(name);
}
