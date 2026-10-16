import ForecastOverride from './forecast_override.svelte';

function mountEditor(roles: string[]) {
	cy.intercept('GET', '**/techs/list', {
		body: { techs: [{ name: 'Ada Lovelace', shift: 'AM' }] }
	}).as('techs');

	cy.mount(ForecastOverride, {
		props: {
			edit: {
				date: '2025-01-15',
				ap: 'AM',
				techs: [],
				orig: [],
				fullname: 'Shop Tech',
				email: 'shop@example.com',
				roles
			},
			on_update: cy.stub().as('on_update')
		}
	});
}

describe('forecast override editor', () => {
	it('prevents generic shop techs from saving schedule edits', () => {
		mountEditor(['Shop Tech']);
		cy.contains('button', 'Save').should('be.disabled');
		cy.contains('logged in to modify the shift schedule').should('be.visible');
	});

	it('allows tech leads to save schedule edits', () => {
		mountEditor(['Tech Lead']);
		cy.contains('button', 'Save').should('be.enabled');
	});
});
