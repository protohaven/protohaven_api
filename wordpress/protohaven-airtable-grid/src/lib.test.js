import React from 'react';
import ReactDOMServer from 'react-dom/server';
import { render_grid } from './lib';

const attributes = {
	imgSize: '120px',
	titleField: 'Title',
	subtitleField: 'Subtitle',
	imgField: 'Image',
	bodyField: 'Body',
	refField: 'Ref',
	refText: 'More',
};

describe('render_grid', () => {
	test('renders fields for a row with an image', () => {
		const data = [
			{
				id: 'rec1',
				fields: {
					Image: [{ thumbnails: { large: { url: 'https://example.test/image.jpg' } } }],
					Title: 'Example Title',
					Subtitle: 'Example Subtitle',
					Body: 'Example Body',
					Ref: 'https://example.test/more',
				},
			},
		];

		const html = ReactDOMServer.renderToStaticMarkup(render_grid(data, attributes));

		expect(html).toContain('https://example.test/image.jpg');
		expect(html).toContain('Example Title');
		expect(html).toContain('Example Subtitle');
		expect(html).toContain('Example Body');
		expect(html).toContain('https://example.test/more');
		expect(html).toContain('More');
	});

	test('skips rows without an image and warns', () => {
		const warn = jest.spyOn(console, 'warn').mockImplementation(() => {});
		const data = [
			{
				id: 'rec2',
				fields: {
					Image: [],
					Title: 'No Image Row',
				},
			},
		];

		const html = ReactDOMServer.renderToStaticMarkup(render_grid(data, attributes));

		expect(html).not.toContain('No Image Row');
		expect(warn).toHaveBeenCalled();
		warn.mockRestore();
	});
});
