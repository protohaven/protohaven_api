import { describe, expect, it } from 'vitest';
import { days_between, formatTime, isToday, pad_calendar_dates, parseLocalDate } from './dates';

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

	it('parses date-only values as local dates, not UTC', () => {
		expect(parseLocalDate('2026-11-07').getDay()).toBe(6); // Saturday
		expect(parseLocalDate('2026-11-07').getDate()).toBe(7);
	});

	it('pads calendar dates to full Sunday-Saturday weeks', () => {
		process.env.TZ = 'America/New_York';
		const padded = pad_calendar_dates([
			'2026-11-04',
			'2026-11-05',
			'2026-11-06',
			'2026-11-07',
			'2026-11-08',
			'2026-11-09',
			'2026-11-10',
			'2026-11-11',
			'2026-11-12',
			'2026-11-13',
			'2026-11-14',
			'2026-11-15',
			'2026-11-16',
			'2026-11-17',
			'2026-11-18'
		]);

		expect(padded.map((d) => d.date)).toEqual([
			'2026-11-01',
			'2026-11-02',
			'2026-11-03',
			'2026-11-04',
			'2026-11-05',
			'2026-11-06',
			'2026-11-07',
			'2026-11-08',
			'2026-11-09',
			'2026-11-10',
			'2026-11-11',
			'2026-11-12',
			'2026-11-13',
			'2026-11-14',
			'2026-11-15',
			'2026-11-16',
			'2026-11-17',
			'2026-11-18',
			'2026-11-19',
			'2026-11-20',
			'2026-11-21'
		]);
		expect(padded[0]).toEqual({ date: '2026-11-01', filler: true });
		expect(padded[6]).toEqual({ date: '2026-11-07' });
		expect(padded[padded.length - 1]).toEqual({ date: '2026-11-21', filler: true });
	});

	it('calculates days between two dates', () => {
		expect(days_between('2026-03-12', '2026-03-26')).toBe(14);
	});
});
