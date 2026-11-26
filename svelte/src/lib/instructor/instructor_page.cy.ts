import Page from '../../routes/instructor/+page.svelte';

function mountInstructorPage(profile: Record<string, unknown>) {
	cy.intercept('GET', '**/whoami', {
		body: { fullname: 'Ada Lovelace', email: 'ada@example.com', roles: [] }
	}).as('whoami');
	cy.intercept('GET', '**/instructor/about*', { body: profile }).as('about');
	cy.intercept('GET', '**/instructor/submissions*', { body: {} }).as('submissions');
	cy.intercept('GET', '**/instructor/logged_hours*', {
		body: {
			logs: [
				{
					timestamp: '2025-01-03T10:00:00',
					class_name: 'Metalworking 101',
					class_date: '2025-01-03',
					hours: '4',
					clearances: '',
					tools: 'Metal Chopsaw',
					students_passed: 'student@example.com'
				}
			]
		}
	}).as('loggedHours');
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

	it('shows read-only logged hours with a submission callout', () => {
		mountInstructorPage({
			active_membership: 'OK',
			capabilities_listed: 'OK',
			paperwork: 'OK',
			discord_user: 'OK'
		});

		cy.contains('a', 'Logged Hours').click();
		cy.wait('@loggedHours');

		cy.contains(
			'This is a read-only view of your instructor hours and clearance logs submitted in the last 6 months.'
		).should('be.visible');
		cy.contains('Metalworking 101').should('be.visible');
		cy.contains('Metal Chopsaw').should('be.visible');
		cy.contains('student@example.com').should('be.visible');
	});

	it('shows a standalone link to submit a private instruction log', () => {
		mountInstructorPage({
			active_membership: 'OK',
			capabilities_listed: 'OK',
			paperwork: 'OK',
			discord_user: 'OK'
		});

		cy.contains('a', 'Private Instruction Log')
			.should('have.attr', 'href')
			.and(
				'include',
				'entry.654625226=Private+Instruction&entry.362496408=Nope,+just+a+single+session+class'
			);
		cy.contains('a', 'Private Instruction Log').should('have.attr', 'target', '_blank');
	});
});
