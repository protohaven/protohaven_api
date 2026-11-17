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

	it('returns the earliest and latest sign-in times for each weekday', () => {
		const thursday = new Date(2026, 2, 26, 12, 0, 0);
		const laterThursday = new Date(2026, 2, 26, 18, 30, 0);
		const friday = new Date(2026, 2, 27, 9, 15, 0);

		const { time_ranges } = calculate_day_of_week_stats([
			{ created: thursday },
			{ created: laterThursday },
			{ created: friday }
		]);

		const thursdayRange = time_ranges[DAY_NAMES[thursday.getDay()]];
		const fridayRange = time_ranges[DAY_NAMES[friday.getDay()]];
		expect(thursdayRange?.earliest).toEqual(thursday);
		expect(thursdayRange?.latest).toEqual(laterThursday);
		expect(fridayRange?.earliest).toEqual(friday);
		expect(fridayRange?.latest).toEqual(friday);
	});
});
