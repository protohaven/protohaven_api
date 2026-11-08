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

export function parseLocalDate(date: string | Date): Date {
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

function formatLocalDate(date: Date): string {
	const mm = (date.getMonth() + 1).toString().padStart(2, '0');
	const dd = date.getDate().toString().padStart(2, '0');
	return `${date.getFullYear()}-${mm}-${dd}`;
}

/**
 * Pads a list of date-only strings out to complete Sunday-Saturday weeks.
 *
 * Dates before the first Sunday and after the last Saturday are returned as
 * filler days, while the original dates are preserved in their input order.
 */
export function pad_calendar_dates(dates: string[]): { date: string; filler?: boolean }[] {
	if (dates.length === 0) {
		return [];
	}

	const result: { date: string; filler?: boolean }[] = dates.map((date) => ({
		date
	}));
	let d = parseLocalDate(result[0].date);
	while (d.getDay() !== 0) {
		d.setDate(d.getDate() - 1);
		result.unshift({ date: formatLocalDate(d), filler: true });
	}

	d = parseLocalDate(result[result.length - 1].date);
	while (d.getDay() !== 6) {
		d.setDate(d.getDate() + 1);
		result.push({ date: formatLocalDate(d), filler: true });
	}
	return result;
}
