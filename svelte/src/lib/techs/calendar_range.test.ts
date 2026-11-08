import { describe, expect, it } from 'vitest';
import {
	CALENDAR_END_PARAM,
	CALENDAR_MAX_DAYS,
	CALENDAR_START_PARAM,
	calendar_range_from_url_search,
	calendar_url_search_with_range,
	default_calendar_range
} from './calendar_range';

describe('calendar range URL helpers', () => {
	it('returns the default calendar range', () => {
		expect(default_calendar_range(new Date(2026, 0, 15, 12))).toEqual({
			start_date: '2026-01-12',
			end_date: '2026-01-29'
		});
	});

	it('reads a valid range from URL search params', () => {
		expect(
			calendar_range_from_url_search('?calendar_start=2026-01-12&calendar_end=2026-01-29')
		).toEqual({
			start_date: '2026-01-12',
			end_date: '2026-01-29'
		});
	});

	it('rejects missing or malformed range params', () => {
		expect(calendar_range_from_url_search('')).toBeNull();
		expect(calendar_range_from_url_search('?calendar_start=2026-01-12')).toBeNull();
		expect(
			calendar_range_from_url_search('?calendar_start=not-a-date&calendar_end=2026-01-29')
		).toBeNull();
		expect(
			calendar_range_from_url_search('?calendar_start=2026-02-30&calendar_end=2026-03-01')
		).toBeNull();
	});

	it('rejects ranges that end before they start or exceed the maximum length', () => {
		expect(
			calendar_range_from_url_search('?calendar_start=2026-01-29&calendar_end=2026-01-12')
		).toBeNull();
		expect(
			calendar_range_from_url_search('?calendar_start=2026-01-01&calendar_end=2026-03-03')
		).toBeNull();
	});

	it('writes the range into the existing search params without dropping other params', () => {
		const result = calendar_url_search_with_range(
			'?email=ada%40example.com&calendar_start=2025-01-01',
			'2026-01-12',
			'2026-01-29'
		);
		const params = new URLSearchParams(result);
		expect(params.get('email')).toBe('ada@example.com');
		expect(params.get(CALENDAR_START_PARAM)).toBe('2026-01-12');
		expect(params.get(CALENDAR_END_PARAM)).toBe('2026-01-29');
	});

	it('allows the maximum configured range length', () => {
		const start = '2026-01-01';
		const end = '2026-03-02'; // 60 days later
		expect(
			calendar_range_from_url_search(
				`?${CALENDAR_START_PARAM}=${start}&${CALENDAR_END_PARAM}=${end}`
			)
		).toEqual({ start_date: start, end_date: end });
		expect(CALENDAR_MAX_DAYS).toBe(60);
	});
});
