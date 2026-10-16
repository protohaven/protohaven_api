import Page from '../../routes/staff/+page.svelte';

describe('staff dashboard', () => {
	it('renders the discord summarizer and ops report tabs', () => {
		cy.intercept('GET', '**/whoami', {
			body: { fullname: 'Staff Person', email: 'staff@example.com' }
		}).as('whoami');
		cy.intercept('GET', '**/staff/discord_member_channels', {
			body: ['#general']
		}).as('channels');

		cy.mount(Page);

		cy.contains('Staff Dashboard').should('be.visible');
		cy.contains('Discord Summarizer').should('be.visible');
		cy.contains('Ops Report').should('be.visible');
		cy.wait('@channels');
		cy.contains('label', '#general').should('be.visible');
	});
});
