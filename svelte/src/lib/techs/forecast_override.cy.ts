import ForecastOverride from './forecast_override.svelte';

function mountEditor(roles: string[], received_at?: string) {
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
				received_at,
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

	it('submits the timestamp the calendar data was received', () => {
		cy.intercept('POST', '**/techs/forecast/override', {
			body: { status: 'ok' }
		}).as('save');
		mountEditor(['Tech Lead'], '2025-01-15T12:00:00.000Z');

		cy.contains('button', 'Save').click();
		cy.wait('@save').its('request.body.received_at').should('eq', '2025-01-15T12:00:00.000Z');
	});
});
