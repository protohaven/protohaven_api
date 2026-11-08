import React from 'react';
import ReactDOMServer from 'react-dom/server';
import { ph_events_to_elems, shorten_class_name } from './lib';

describe('shorten_class_name', () => {
	test('removes the area prefix', () => {
		expect(shorten_class_name('Wood 102: Test Clearance')).toBe('Test Clearance');
	});

	test('removes parenthetical suffixes', () => {
		expect(
			shorten_class_name('Graphics 110: Vinyl Cut Signs (Vinyl Cutter Clearance)')
		).toBe('Vinyl Cut Signs');
	});

	test('truncates long class names', () => {
		const longName = 'Textiles 102: ABCDEFGHIJKLMNOPQRSTUVWXYZ 1234567890';
		const shortened = shorten_class_name(longName);

		expect(shortened).toHaveLength(35);
		expect(shortened.endsWith('...')).toBe(true);
	});
});

describe('ph_events_to_elems', () => {
	test('renders event links with dates and low-seat warnings', () => {
		const events = [
			{ name: 'Wood 102: Test Clearance', date: 'Oct 1', seats_left: 2, url: 'https://example.test/1' },
			{ name: 'Graphics 110: Vinyl Cut Signs', date: 'Oct 2', seats_left: 1, url: 'https://example.test/2' },
			{ name: 'Textiles 102: Sewing', date: 'Oct 3', seats_left: 4, url: 'https://example.test/3' },
		];

		const html = ReactDOMServer.renderToStaticMarkup(
			<div>{ph_events_to_elems(events)}</div>
		);

		expect(html).toContain('https://example.test/1');
		expect(html).toContain('2 seats left!');
		expect(html).toContain('https://example.test/2');
		expect(html).toContain('1 seat left!');
		expect(html).toContain('https://example.test/3');
		expect(html).toContain('(Oct 3)');
		expect(html).not.toContain('4 seats left');
	});

	test('skips events without a name', () => {
		const events = [{ date: 'Oct 1', seats_left: 2, url: 'https://example.test/1' }];

		const html = ReactDOMServer.renderToStaticMarkup(
			<div>{ph_events_to_elems(events)}</div>
		);

		expect(html).not.toContain('https://example.test/1');
	});
});
