import { describe, expect, it } from 'vitest';
import { calculate_day_of_week_stats, DAY_NAMES } from './signin_stats';

describe('members utils', () => {
	it('counts unique sign-in dates by day of week', () => {
		const thursday = new Date(2026, 2, 26, 12, 0, 0);
		const friday = new Date(2026, 2, 27, 12, 0, 0);

		const { stats, total_signins } = calculate_day_of_week_stats([
			{ created: thursday },
			{ created: thursday },
			{ created: friday }
		]);

		expect(total_signins).toBe(2);
		expect(stats[DAY_NAMES[thursday.getDay()]]).toBe(1);
		expect(stats[DAY_NAMES[friday.getDay()]]).toBe(1);
	});
});
