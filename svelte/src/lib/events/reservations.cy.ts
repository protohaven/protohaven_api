import Reservations from './reservations.svelte';

const reservations = [
	{
		id: 1,
		name: 'Ada Lovelace',
		area: 'Woodshop',
		resource: 'Table Saw',
		start: '9:00 AM',
		end: '11:00 AM',
		ts: '2025-01-15T09:00:00'
	},
	{
		id: 2,
		name: 'Ada Lovelace',
		area: 'Woodshop',
		resource: 'Planer',
		start: '10:00 AM',
		end: '12:00 PM',
		ts: '2025-01-15T10:00:00'
	},
	{
		id: 3,
		name: 'Grace Hopper',
		area: 'Metal Shop',
		resource: 'Mill',
		start: '1:00 PM',
		end: '3:00 PM',
		ts: '2025-01-15T13:00:00'
	}
];

function mountReservations() {
	cy.intercept('GET', '**/events/reservations', { body: reservations }).as('reservations');
	cy.mount(Reservations);
	cy.wait('@reservations');
}

describe('events reservations', () => {
	it('shows reservations grouped by owner and area', () => {
		mountReservations();

		cy.contains('Ada Lovelace').should('be.visible');
		cy.contains('Grace Hopper').should('be.visible');
		cy.contains('Woodshop (2 resources, 9:00 AM, 10:00 AM)').should('be.visible');
		cy.contains('Metal Shop (1 resources, 1:00 PM)').should('be.visible');
	});

	it('shows more details on hover', () => {
		mountReservations();

		cy.get('#res-1').trigger('mouseover');
		cy.get('.tooltip').should('be.visible');
		cy.get('.tooltip').should('contain', 'Table Saw');
		cy.get('.tooltip').should('contain', '9:00 AM - 11:00 AM');
		cy.get('.tooltip').should('contain', 'Planer');
	});
});
