import { describe, expect, it } from 'vitest';
import { is_instructor_onboarded } from './types';

describe('is_instructor_onboarded', () => {
	it('returns false for a missing profile', () => {
		expect(is_instructor_onboarded(null)).toBe(false);
		expect(is_instructor_onboarded(undefined)).toBe(false);
	});

	it('returns false when any onboarding field lacks OK', () => {
		expect(
			is_instructor_onboarded({
				active_membership: 'OK',
				capabilities_listed: 'OK',
				paperwork: 'missing',
				discord_user: 'OK'
			})
		).toBe(false);
	});

	it('returns true when all onboarding fields are OK', () => {
		expect(
			is_instructor_onboarded({
				active_membership: 'OK',
				capabilities_listed: 'OK',
				paperwork: 'OK',
				discord_user: 'ok'
			})
		).toBe(true);
	});
});
