import Members from './members.svelte';

describe('techs members', () => {
	it('shows access denied when not logged in', () => {
		cy.mount(Members, {
			props: {
				visible: true,
				user: null
			}
		});

		cy.contains('Access denied').should('be.visible');
		cy.get('input[aria-label="Search members by name or email"]').should('not.exist');
	});

	it('allows shop techs to search member sign-ins', () => {
		cy.intercept('GET', '**/techs/members*', { body: [] }).as('members');
		cy.intercept('POST', '**/neon_lookup*', {
			body: [{ name: 'Ada Lovelace', email: 'ada@example.com' }]
		}).as('lookup');

		cy.mount(Members, {
			props: {
				visible: true,
				user: { roles: ['Shop Tech'], fullname: 'Shop Tech', email: 'tech@example.com' }
			}
		});
		cy.wait('@members');

		cy.get('input[aria-label="Search members by name or email"]').type('Ada');
		cy.wait('@lookup');
		cy.contains('Ada Lovelace (ada@example.com)').should('be.visible');
	});

	it('shows sign-in time ranges for a selected member', () => {
		const thursday = new Date(2026, 2, 26, 12, 0, 0).toISOString();
		const laterThursday = new Date(2026, 2, 26, 18, 30, 0).toISOString();

		cy.intercept('GET', '**/techs/members*', {
			body: [
				{
					name: 'Ada Lovelace',
					email: 'ada@example.com',
					member: true,
					status: 'Active',
					clearances: [],
					violations: [],
					created: thursday
				},
				{
					name: 'Ada Lovelace',
					email: 'ada@example.com',
					member: true,
					status: 'Active',
					clearances: [],
					violations: [],
					created: laterThursday
				}
			]
		}).as('members');
		cy.intercept('POST', '**/neon_lookup*', {
			body: [{ name: 'Ada Lovelace', email: 'ada@example.com' }]
		}).as('lookup');

		cy.mount(Members, {
			props: {
				visible: true,
				user: { roles: ['Shop Tech'], fullname: 'Shop Tech', email: 'tech@example.com' }
			}
		});
		cy.wait('@members');

		cy.get('input[aria-label="Search members by name or email"]').type('Ada');
		cy.wait('@lookup');
		cy.contains('Ada Lovelace (ada@example.com)').click();
		cy.wait('@members');

		cy.contains('Sign-in Time Range').should('be.visible');
		cy.contains('12:00 PM - 6:30 PM').should('be.visible');
	});
});
