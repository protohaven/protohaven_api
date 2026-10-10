export interface Reservation {
	name: string;
	area: string;
	id?: string | number;
	resource?: string;
	start?: string;
	end?: string;
	ts?: string;
}

export function groupReservations(reservations: Reservation[]) {
	const grouped: Record<string, Record<string, Reservation[]>> = {};

	for (const reservation of reservations) {
		const owner = reservation.name;
		const area = reservation.area;

		if (!grouped[owner]) {
			grouped[owner] = {};
		}

		if (!grouped[owner][area]) {
			grouped[owner][area] = [];
		}

		grouped[owner][area].push(reservation);
	}

	return grouped;
}

export function uniqueStarts(reservations: Reservation[]) {
	const uniques: Record<string, string | undefined> = {};
	for (const r of reservations) {
		uniques[r.start ?? ''] = r.ts;
	}
	const sorted = Array.from(Object.entries(uniques)).sort((a, b) => {
		const aTs = a[1] ?? '';
		const bTs = b[1] ?? '';
		return bTs < aTs ? 1 : bTs > aTs ? -1 : 0;
	});
	return sorted.map((a) => a[0]).join(', ');
}
