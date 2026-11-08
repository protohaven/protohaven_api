import { isodate } from '$lib/api';
import { days_between, parseLocalDate } from '$lib/dates';

export const CALENDAR_START_PARAM = 'calendar_start';
export const CALENDAR_END_PARAM = 'calendar_end';
export const CALENDAR_MAX_DAYS = 60;
export const CALENDAR_DEFAULT_TRAIL_DAYS = 3;
export const CALENDAR_DEFAULT_DURATION_DAYS = 14;

function normalize_date(value: string | null): string | null {
	if (!value || !/^\d{4}-\d{2}-\d{2}$/.test(value)) {
		return null;
	}
	const parsed = parseLocalDate(value);
	if (Number.isNaN(parsed.getTime())) {
		return null;
	}
	const normalized = isodate(parsed);
	return normalized === value ? normalized : null;
}

export function default_calendar_range(
	now = new Date(),
	trail_days = CALENDAR_DEFAULT_TRAIL_DAYS,
	duration_days = CALENDAR_DEFAULT_DURATION_DAYS
): { start_date: string; end_date: string } {
	const start = new Date(now);
	const end = new Date(now);
	start.setDate(start.getDate() - trail_days);
	end.setDate(end.getDate() + duration_days);
	return {
		start_date: isodate(start),
		end_date: isodate(end)
	};
}

export function calendar_range_from_url_search(
	search: string,
	max_days = CALENDAR_MAX_DAYS
): { start_date: string; end_date: string } | null {
	const params = new URLSearchParams(search);
	const start_date = normalize_date(params.get(CALENDAR_START_PARAM));
	const end_date = normalize_date(params.get(CALENDAR_END_PARAM));
	if (!start_date || !end_date) {
		return null;
	}
	if (parseLocalDate(end_date) < parseLocalDate(start_date)) {
		return null;
	}
	if (days_between(start_date, end_date) > max_days) {
		return null;
	}
	return { start_date, end_date };
}

export function calendar_url_search_with_range(
	search: string,
	start_date: string,
	end_date: string
): string {
	const params = new URLSearchParams(search);
	params.set(CALENDAR_START_PARAM, start_date);
	params.set(CALENDAR_END_PARAM, end_date);
	return params.toString();
}
