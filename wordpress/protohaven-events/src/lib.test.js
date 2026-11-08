import { extraFromName, fetch_events, LEVELS } from './lib';

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
