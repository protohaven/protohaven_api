import { describe, expect, it } from 'vitest';
import { days_between, formatTime, isToday } from './dates';

describe('date/time helpers', () => {
	it('returns Never for an empty timestamp', () => {
		expect(formatTime('')).toBe('Never');
	});

	it('formats valid timestamps with a colon', () => {
		expect(formatTime('2026-03-26T12:34:00')).toMatch(/\d{1,2}:\d{2}/);
	});

	it('recognizes the local calendar day', () => {
		const now = new Date(2026, 2, 26, 12, 0, 0);
		expect(isToday('2026-03-26', now)).toBe(true);
		expect(isToday('2026-03-27', now)).toBe(false);
	});

	it('calculates days between two dates', () => {
		expect(days_between('2026-03-12', '2026-03-26')).toBe(14);
	});
});
