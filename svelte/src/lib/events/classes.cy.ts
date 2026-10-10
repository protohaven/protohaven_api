import Classes from './classes.svelte';

const upcoming = {
	now: '2025-01-15T12:00:00-05:00',
	events: [
		{
			id: '111',
			name: 'Neon Class: Intro to Woodshop',
			instructor: 'Ada Lovelace',
			start: '2025-01-15T18:00:00-05:00',
			end: '2025-01-15T21:00:00-05:00',
			capacity: 6,
			registration: true
		},
		{
			id: '222',
			name: 'Eventbrite Class: Metal Lathe Basics',
			instructor: 'Grace Hopper',
			start: '2025-01-16T10:00:00-05:00',
			end: '2025-01-16T13:00:00-05:00',
			capacity: 8,
			registration: false
		}
	]
};

function mountClasses() {
	cy.intercept('GET', '**/events/upcoming', { body: upcoming }).as('upcoming');
	cy.intercept('GET', '**/events/attendees?id=111', { body: '5' }).as('attendees111');
	cy.intercept('GET', '**/events/attendees?id=222', { body: '3' }).as('attendees222');

	cy.mount(Classes);
	cy.wait('@upcoming');
	cy.wait('@attendees111');
	cy.wait('@attendees222');
}

describe('events classes', () => {
	it('shows classes including instructor and attendee data', () => {
		mountClasses();

		cy.contains('Neon Class: Intro to Woodshop').should('be.visible');
		cy.contains('Ada Lovelace').should('be.visible');
		cy.contains('Eventbrite Class: Metal Lathe Basics').should('be.visible');
		cy.contains('Grace Hopper').should('be.visible');

		cy.contains('tr', 'Neon Class: Intro to Woodshop').find('.attendees').should('contain', '5');
		cy.contains('tr', 'Eventbrite Class: Metal Lathe Basics')
			.find('.attendees')
			.should('contain', '3');

		cy.contains('open').should('be.visible');
		cy.contains('closed').should('be.visible');
	});
});
