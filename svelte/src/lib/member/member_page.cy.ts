import MemberPage from '../../routes/member/+page.svelte';

function mountPage(roles: string[], recertBody: unknown, recertStatus = 200) {
	cy.intercept('GET', '**/whoami', {
		body: {
			fullname: 'Test Member',
			email: 'member@example.com',
			neon_id: '123',
			roles,
			clearances: ['Woodshop'],
			event_discount_pct: 0
		}
	}).as('whoami');

	cy.intercept('GET', '**/member/recert_data', {
		statusCode: recertStatus,
		body: recertBody
	}).as('recert');

	cy.intercept('GET', '**/class_listing', { body: [] }).as('classListing');

	cy.mount(MemberPage);
	cy.wait('@whoami');
	cy.wait('@recert');
}

function mountDiscordSetup() {
	cy.intercept('GET', '**/whoami', {
		body: {
			fullname: 'Test Member',
			email: 'member@example.com',
			neon_id: '123',
			roles: ['Member'],
			clearances: ['Woodshop'],
			event_discount_pct: 0
		}
	}).as('whoami');

	cy.intercept('GET', '**/member/recert_data', {
		statusCode: 503,
		body: 'Not yet enabled'
	}).as('recert');

	cy.intercept('GET', '**/class_listing', { body: [] }).as('classListing');
	cy.intercept('POST', '**/member/set_discord', { accountId: '123' }).as('setDiscord');

	cy.window().then((win) => {
		win.history.pushState({}, '', '/?discord_id=asdf&neon_id=123');
	});
	cy.mount(MemberPage);
	cy.wait('@whoami');
	cy.wait('@recert');
}

describe('member dashboard', () => {
	it('shows clickable Shop Status and Instructor Dashboard links and logout', () => {
		mountPage(['Instructor'], 'Not yet enabled', 503);

		cy.contains('a', 'Logout').should('be.visible').and('have.attr', 'href', '/logout');
		cy.contains('a', 'Shop Status').should('be.visible').and('have.attr', 'href', '/events');
		cy.contains('a', 'Instructor Dashboard')
			.should('be.visible')
			.and('have.attr', 'href', '/instructor');
	});

	it('does not show Instructor Dashboard for non-instructor roles', () => {
		mountPage(['Member'], 'Not yet enabled', 503);

		cy.contains('a', 'Shop Status').should('be.visible');
		cy.contains('a', 'Instructor Dashboard').should('not.exist');
	});

	it('hides the recertification tab when the member has not opted in', () => {
		mountPage(['Instructor'], 'Not yet enabled', 503);

		cy.contains('a', 'Recertification').should('not.exist');
	});

	it('shows the recertification tab when the member has opted in', () => {
		mountPage(['Instructor'], { pending: [], configs: [] });

		cy.contains('a', 'Recertification').should('be.visible');
	});

	it('shows and submits the discord association form', () => {
		mountDiscordSetup();

		cy.contains('Discord Account').should('be.visible');
		cy.get('input').should('have.value', 'asdf');
		cy.contains('button', 'Save').click();

		cy.wait('@setDiscord')
			.its('request.body')
			.should('deep.equal', { discord_id: 'asdf', neon_id: '123' });
		cy.contains('Discord user set successfully.').should('be.visible');
	});
});
