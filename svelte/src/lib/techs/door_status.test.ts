import { describe, expect, it } from 'vitest';
import { doorSummary } from './door_status';

describe('door status', () => {
	it('summarizes offline doors', () => {
		expect(doorSummary({ name: 'Front Door', is_online: false })).toBe('Front Door: Offline');
	});

	it('summarizes open and closed doors', () => {
		expect(doorSummary({ name: 'Front Door', is_online: true, open_close_state: true })).toBe(
			'Front Door: OPEN'
		);
		expect(doorSummary({ name: 'Front Door', is_online: true, open_close_state: false })).toBe(
			'Front Door: CLOSED'
		);
	});
});
