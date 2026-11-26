import { dateFromInputValue, extraFromName, fetch_events, LEVELS } from './lib';

describe('extraFromName', () => {
	test('parses area, level, title, and parenthetical suffix', () => {
		expect(extraFromName('Graphics 111: Printed Mugs (Dye Sublimation Clearance)')).toEqual({
			area: 'Graphics',
			level: 111,
			levelDesc: 'Beginner Project',
			title: 'Printed Mugs',
		});
	});

	test('parses names without a numeric level', () => {
		expect(extraFromName('Graphics: Printed Mugs')).toEqual({
			area: 'Graphics',
			level: null,
			levelDesc: '',
			title: 'Printed Mugs',
		});
	});

	test('marks uncategorized names as special events', () => {
		expect(extraFromName('Printed Mugs')).toEqual({
			area: 'Special Event',
			level: null,
			title: 'Printed Mugs',
		});
	});
});

describe('LEVELS', () => {
	test('maps levels from highest to lowest', () => {
		expect(LEVELS).toEqual([
			[200, 'Intermediate'],
			[110, 'Beginner Project'],
			[100, 'Beginner Skills'],
		]);
	});
});

describe('dateFromInputValue', () => {
	test('returns null for an empty value', () => {
		expect(dateFromInputValue('')).toBeNull();
		expect(dateFromInputValue(null)).toBeNull();
	});

	test('parses yyyy-mm-dd as local midnight', () => {
		const d = dateFromInputValue('2024-10-24');
		expect(d.getFullYear()).toBe(2024);
		expect(d.getMonth()).toBe(9); // October is zero-indexed
		expect(d.getDate()).toBe(24);
		expect(d.getHours()).toBe(0);
		expect(d.getMinutes()).toBe(0);
	});
});

describe('fetch_events', () => {
	const originalFetch = global.fetch;

	afterEach(() => {
		global.fetch = originalFetch;
	});

	test('returns event data from the first successful fetch', async () => {
		const events = [{ name: 'Wood 101' }];
		global.fetch = jest.fn().mockResolvedValue({
			ok: true,
			json: async () => ({ events }),
		});

		await expect(fetch_events(3, 1000)).resolves.toEqual({ events });
	});
});
