import { describe, expect, it } from 'vitest';
import { as_datetimelocal, isodate, isodatetime, parse_8601_basic } from './api';

describe('api date helpers', () => {
	it('formats local dates without shifting to UTC', () => {
		expect(isodate(new Date(2026, 2, 26, 12, 0, 0))).toBe('2026-03-26');
		// Late-evening local dates must stay on the local calendar day.
		expect(isodate(new Date(2026, 2, 26, 20, 0, 0))).toBe('2026-03-26');
	});

	it('parses date-only strings in local time', () => {
		expect(isodate('2026-03-26')).toBe('2026-03-26');
	});

	it('returns an explicit UTC ISO timestamp', () => {
		expect(isodatetime('2026-03-26T12:00:00Z')).toBe('2026-03-26T12:00:00Z');
	});

	it('parses compact ISO 8601 timestamps as UTC', () => {
		expect(parse_8601_basic('20260326T120000').toISOString()).toBe('2026-03-26T12:00:00.000Z');
	});

	it('formats values for datetime-local inputs', () => {
		expect(as_datetimelocal('2026-03-26T12:00:00Z')).toMatch(/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}$/);
	});
});
