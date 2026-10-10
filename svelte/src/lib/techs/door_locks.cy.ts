import DoorLocks from './door_locks.svelte';

describe('techs door locks', () => {
	it('is hidden when not visible', () => {
		cy.intercept('GET', '**/techs/door_locks', { body: { doors: [] } }).as('doors');
		cy.mount(DoorLocks, { props: { visible: false } });
		cy.get('.door-locks-status').should('not.exist');
	});

	it('shows a warning badge with open and offline door counts', () => {
		cy.intercept('GET', '**/techs/door_locks', {
			body: {
				doors: [
					{
						name: 'Front Door',
						mac: '00:11:22:33:44:55',
						is_online: true,
						open_close_state: true
					},
					{
						name: 'Back Door',
						mac: 'AA:BB:CC:DD:EE:FF',
						is_online: false,
						open_close_state: false
					}
				],
				timestamp: '2025-01-01T12:00:00-05:00'
			}
		}).as('doors');

		cy.mount(DoorLocks, { props: { visible: true } });
		cy.wait('@doors');

		cy.get('#door-status-badge').should('contain', '1 open').and('contain', '1 offline');
	});

	it('shows a success badge when all doors are closed and online', () => {
		cy.intercept('GET', '**/techs/door_locks', {
			body: {
				doors: [
					{
						name: 'Front Door',
						mac: '00:11:22:33:44:55',
						is_online: true,
						open_close_state: false
					}
				],
				timestamp: '2025-01-01T12:00:00-05:00'
			}
		}).as('doors');

		cy.mount(DoorLocks, { props: { visible: true } });
		cy.wait('@doors');

		cy.get('#door-status-badge').should('contain', '✓');
	});
});
