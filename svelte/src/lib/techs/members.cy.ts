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
});
