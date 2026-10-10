export function formatTime(timestamp: string): string {
	if (!timestamp) return 'Never';
	try {
		const date = new Date(timestamp);
		return date.toLocaleTimeString('en-US', {
			hour: '2-digit',
			minute: '2-digit',
			hour12: true
		});
	} catch {
		return 'Invalid time';
	}
}

interface DoorState {
	name: string;
	is_online: boolean;
	open_close_state?: boolean;
}

export function doorSummary(door: DoorState): string {
	if (!door.is_online) return `${door.name}: Offline`;
	return `${door.name}: ${door.open_close_state ? 'OPEN' : 'CLOSED'}`;
}
