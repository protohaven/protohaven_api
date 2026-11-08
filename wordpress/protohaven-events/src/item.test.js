import { createElement } from 'react';
import { renderToStaticMarkup } from 'react-dom/server';

import { Item } from './item';

function renderItem( user ) {
	const times = [
		[
			'evt123',
			{
				d0: new Date( '2026-01-01T12:00:00-05:00' ),
				d1: new Date( '2026-01-01T15:00:00-05:00' ),
				capacity: 10,
				sold: 2,
				url: 'https://www.eventbrite.com/e/123/',
				price: 50,
				discount: 40,
			},
		],
	];

	return renderToStaticMarkup(
		createElement( Item, {
			title: 'Test Class',
			area: 'Test Area',
			desc: 'Test Description',
			levelDesc: 'Beginner Skills',
			age: 16,
			features: null,
			img: null,
			times,
			humanized_info: null,
			visible: true,
			user,
			base_url: 'https://api.protohaven.org',
		} )
	);
}

const DISCOUNT_URL =
	'href="https://api.protohaven.org/member/goto_class?url=https%3A%2F%2Fwww.eventbrite.com%2Fe%2F123%2F"';
const EVENTBRITE_URL = 'href="https://www.eventbrite.com/e/123/"';

function count( haystack, needle ) {
	return haystack.split( needle ).length - 1;
}

describe( 'Item links', () => {
	test( 'date and more links use the member discount interstitial when logged in', () => {
		const html = renderItem( { neon_id: 123 } );
		expect( count( html, DISCOUNT_URL ) ).toBe( 2 );
	} );

	test( 'date and more links go directly to Eventbrite when not logged in', () => {
		const html = renderItem( {} );
		expect( count( html, EVENTBRITE_URL ) ).toBe( 2 );
	} );
} );
