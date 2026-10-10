import Splash from './splash.svelte';

describe('Splash', () => {
	it('mounts', () => {
		cy.mount(Splash);
	});

	it('does not allow sign-in with an empty or whitespace-only email', () => {
		cy.mount(Splash);

		cy.contains('button', 'Member').should('be.disabled');
		cy.contains('button', 'Guest').should('be.disabled');

		cy.get('input[type="email"]').first().type('   ');
		cy.contains('button', 'Member').should('be.disabled');
		cy.contains('button', 'Guest').should('be.disabled');

		cy.get('input[type="email"]').first().clear().type('member@example.com');
		cy.contains('button', 'Member').should('be.enabled');
		cy.contains('button', 'Guest').should('be.enabled');
	});

	it('delegates member and guest sign-in clicks', () => {
		cy.mount(Splash, {
			props: {
				on_member: cy.stub().as('on_member'),
				on_guest: cy.stub().as('on_guest'),
				feedback: null,
				email: '',
				progress: null,
				dependent_info: ''
			}
		});

		cy.get('input[type="email"]').first().type('member@example.com');
		cy.contains('button', 'Member').click();
		cy.get('@on_member').should('have.been.calledOnce');

		cy.contains('button', 'Guest').click();
		cy.get('@on_guest').should('have.been.calledOnce');
	});

	it('requires dependent info when signing in children', () => {
		cy.mount(Splash);

		cy.get('input[type="email"]').first().type('member@example.com');
		cy.contains('button', 'Member').should('be.enabled');

		cy.get('input[type="checkbox"]').check();
		cy.contains('button', 'Member').should('be.disabled');
		cy.contains('button', 'Guest').should('be.disabled');

		cy.get('input[type="email"]').eq(1).type('Child Name');
		cy.contains('button', 'Member').should('be.enabled');
	});
});
