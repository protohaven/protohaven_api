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

	for (const signin of memberSignins) {
		const date = new Date(signin.created);
		const dayOfWeek = date.getDay();
		uniqueDatesByDay[dayOfWeek].add(isodate(date));
	}

	for (let i = 0; i < 7; i++) {
		stats[DAY_NAMES[i]] = uniqueDatesByDay[i].size;
	}

	return {
		stats,
		total_signins: Object.values(stats).reduce((sum, count) => sum + count, 0)
	};
}
