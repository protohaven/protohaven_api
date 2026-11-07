import Scheduler from './scheduler.svelte';

const templates = {
	'cls-1': {
		class_id: 'cls-1',
		name: 'Laser 101',
		hours: [3],
		capacity: 4,
		price: 50,
		period: 14,
		areas: ['Laser'],
		clearances: []
	}
};

describe('class scheduler', () => {
	it('renders a 6pm session start as 06:00PM', () => {
		cy.intercept('POST', '**/instructor/validate*', {
			body: { valid: true, errors: [] }
		}).as('validate');

		cy.mount(Scheduler, {
			props: {
				open: true,
				templates,
				classes: { 'cls-1': 'Laser 101' },
				email: 'instructor@example.com'
			}
		});

		cy.contains('button', '1 option(s)').click();
		cy.contains('Laser 101').click();

		cy.contains('06:00PM').should('be.visible');
		cy.contains('All validation checks passed').should('be.visible');
	});
});
