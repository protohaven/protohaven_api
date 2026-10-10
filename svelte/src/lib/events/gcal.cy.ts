import Gcal from './gcal.svelte';

const events = [
	{ name: 'Woodshop 101', start: '2025-01-15T18:00:00-05:00' },
	{ name: 'Metal Lathe Demo', start: '2025-01-16T10:00:00-05:00' }
];

describe('events gcal', () => {
	it('displays upcoming calendar events', () => {
		cy.intercept('GET', '**/events/shop', { body: events }).as('shop');
		cy.mount(Gcal);
		cy.wait('@shop');

		cy.contains('Upcoming Shop Events').should('be.visible');
		cy.contains('Woodshop 101').should('be.visible');
		cy.contains('Metal Lathe Demo').should('be.visible');

		const expectedDate = new Date(events[0].start).toLocaleString('en-US', {
			timeZone: 'America/New_York'
		});
		cy.contains(expectedDate).should('be.visible');
	});
});
