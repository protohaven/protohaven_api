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

function parseLocalDate(date: string | Date): Date {
	if (date instanceof Date) return date;
	// Use local noon for date-only strings so `getDate()` does not shift to
	// the previous calendar day in UTC-negative time zones.
	return date.includes('T') ? new Date(date) : new Date(`${date}T12:00:00`);
}

export function isToday(date: string | Date, now = new Date()): boolean {
	const parsed = parseLocalDate(date);
	return (
		now.getFullYear() === parsed.getFullYear() &&
		now.getMonth() === parsed.getMonth() &&
		now.getDate() === parsed.getDate()
	);
}

export function days_between(d1: string | Date, d2: string | Date): number {
	// https://stackoverflow.com/a/2627493
	return Math.round(
		Math.abs((parseLocalDate(d2).getTime() - parseLocalDate(d1).getTime()) / (24 * 60 * 60 * 1000))
	);
}
