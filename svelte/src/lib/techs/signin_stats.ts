import { isodate } from '$lib/api';

export const DAY_NAMES = [
	'Sunday',
	'Monday',
	'Tuesday',
	'Wednesday',
	'Thursday',
	'Friday',
	'Saturday'
] as const;

type DayName = (typeof DAY_NAMES)[number];

export type DayTimeRange = {
	earliest: Date;
	latest: Date;
};

interface MemberSignin {
	created: Date | string;
}

export function calculate_day_of_week_stats(memberSignins: MemberSignin[]) {
	const stats = {
		Sunday: 0,
		Monday: 0,
		Tuesday: 0,
		Wednesday: 0,
		Thursday: 0,
		Friday: 0,
		Saturday: 0
	};
	const uniqueDatesByDay: Record<number, Set<string>> = {
		0: new Set(),
		1: new Set(),
		2: new Set(),
		3: new Set(),
		4: new Set(),
		5: new Set(),
		6: new Set()
	};
	const timeRangesByDay: Record<number, DayTimeRange> = {
		0: { earliest: new Date(8640000000000000), latest: new Date(0) },
		1: { earliest: new Date(8640000000000000), latest: new Date(0) },
		2: { earliest: new Date(8640000000000000), latest: new Date(0) },
		3: { earliest: new Date(8640000000000000), latest: new Date(0) },
		4: { earliest: new Date(8640000000000000), latest: new Date(0) },
		5: { earliest: new Date(8640000000000000), latest: new Date(0) },
		6: { earliest: new Date(8640000000000000), latest: new Date(0) }
	};

	for (const signin of memberSignins) {
		const date = new Date(signin.created);
		const dayOfWeek = date.getDay();
		uniqueDatesByDay[dayOfWeek].add(isodate(date));

		if (date < timeRangesByDay[dayOfWeek].earliest) {
			timeRangesByDay[dayOfWeek].earliest = date;
		}
		if (date > timeRangesByDay[dayOfWeek].latest) {
			timeRangesByDay[dayOfWeek].latest = date;
		}
	}

	for (let i = 0; i < 7; i++) {
		stats[DAY_NAMES[i]] = uniqueDatesByDay[i].size;
	}

	const time_ranges = Object.fromEntries(
		DAY_NAMES.map((day, i) => {
			if (uniqueDatesByDay[i].size === 0) {
				return [day, null];
			}
			return [day, timeRangesByDay[i]];
		})
	) as Record<DayName, DayTimeRange | null>;

	return {
		stats,
		total_signins: Object.values(stats).reduce((sum, count) => sum + count, 0),
		time_ranges
	};
}
