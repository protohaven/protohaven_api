export function isToday(date, now = new Date()) {
	// Apply time zone to prevent day offset.
	date = new Date(date + ' EST');
	return (
		now.getFullYear() === date.getFullYear() &&
		now.getMonth() === date.getMonth() &&
		now.getDate() === date.getDate()
	);
}

export function days_between(d1, d2) {
	// https://stackoverflow.com/a/2627493
	return Math.round(Math.abs((new Date(d2) - new Date(d1)) / (24 * 60 * 60 * 1000)));
}
