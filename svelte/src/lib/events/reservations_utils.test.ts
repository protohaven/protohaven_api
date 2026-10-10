import { describe, expect, it } from 'vitest';
import { groupReservations, uniqueStarts } from './reservations_utils';

describe('reservations utils', () => {
	it('groups reservations by owner and area', () => {
		const result = groupReservations([
			{ id: 1, name: 'Ada', area: 'Woodshop', resource: 'Table Saw' },
			{ id: 2, name: 'Ada', area: 'Woodshop', resource: 'Planer' },
			{ id: 3, name: 'Ada', area: 'Metal Shop', resource: 'Mill' },
			{ id: 4, name: 'Grace', area: 'Woodshop', resource: 'Table Saw' }
		]);

		expect(Object.keys(result)).toEqual(['Ada', 'Grace']);
		expect(Object.keys(result.Ada)).toEqual(['Woodshop', 'Metal Shop']);
		expect(result.Ada.Woodshop.map((r) => r.id)).toEqual([1, 2]);
	});

	it('sorts unique start times by timestamp', () => {
		const starts = uniqueStarts([
			{ start: '9:00 AM', ts: '2026-03-26T09:00:00' },
			{ start: '11:00 AM', ts: '2026-03-26T11:00:00' },
			{ start: '9:00 AM', ts: '2026-03-26T09:00:00' }
		]);

		expect(starts).toBe('9:00 AM, 11:00 AM');
	});
});
