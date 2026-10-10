import { describe, expect, it } from 'vitest';
import { doorSummary, formatTime } from './door_locks_utils';

describe('door locks utils', () => {
	it('returns Never for an empty timestamp', () => {
		expect(formatTime('')).toBe('Never');
	});

	it('formats valid timestamps with a colon', () => {
		expect(formatTime('2026-03-26T12:34:00')).toMatch(/\d{1,2}:\d{2}/);
	});

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
