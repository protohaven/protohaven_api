import { describe, expect, it } from 'vitest';
import { days_between } from './shifts_utils';

describe('shifts utils', () => {
	it('calculates inclusive range days between two dates', () => {
		expect(days_between('2026-03-12', '2026-03-26')).toBe(14);
	});
});
