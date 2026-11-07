import Page from '../../routes/instructor/+page.svelte';

function mountInstructorPage(profile: Record<string, unknown>) {
	cy.intercept('GET', '**/whoami', {
		body: { fullname: 'Ada Lovelace', email: 'ada@example.com', roles: [] }
	}).as('whoami');
	cy.intercept('GET', '**/instructor/about*', { body: profile }).as('about');
	cy.intercept('GET', '**/instructor/submissions*', { body: {} }).as('submissions');
	cy.intercept('GET', '**/instructor/class_details*', {
		body: { schedule: [] }
	}).as('classDetails');
	cy.mount(Page);
}

describe('instructor dashboard', () => {
	it('shows a warning icon on the profile tab when onboarding is incomplete', () => {
		mountInstructorPage({
			active_membership: 'OK',
			capabilities_listed: 'OK',
			paperwork: 'missing',
			discord_user: 'OK'
		});

		cy.get('i.bi-exclamation-triangle').should('be.visible');
		cy.get('i.bi-check-all').should('not.exist');
	});

	it('shows a check-all icon on the profile tab when onboarding is complete', () => {
		mountInstructorPage({
			active_membership: 'OK',
			capabilities_listed: 'OK',
			paperwork: 'OK',
			discord_user: 'OK'
		});

		cy.get('i.bi-check-all').should('be.visible');
		cy.get('i.bi-exclamation-triangle').should('not.exist');
	});
});
