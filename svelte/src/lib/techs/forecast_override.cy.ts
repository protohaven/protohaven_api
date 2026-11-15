import ForecastOverride from './forecast_override.svelte';

function mountEditor(roles: string[], received_at?: string, fullname: string | null = 'Shop Tech') {
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
				...(fullname !== null ? { fullname } : {}),
				email: fullname !== null ? 'shop@example.com' : undefined,
				received_at,
				roles
			},
			on_update: cy.stub().as('on_update')
		}
	});
}

describe('forecast override editor', () => {
	it('prevents logged out users from saving schedule edits', () => {
		mountEditor([], undefined, null);
		cy.contains('button', 'Save').should('be.disabled');
		cy.contains('logged in to modify the shift schedule').should('be.visible');
	});

	it('warns logged in users without permission instead of asking them to log in', () => {
		mountEditor(['Instructor']);
		cy.contains('button', 'Save').should('be.disabled');
		cy.contains('does not have permission to modify').should('be.visible');
		cy.contains('logged in to modify the shift schedule').should('not.exist');
	});

	it('allows shop tech leads to save schedule edits', () => {
		mountEditor(['Shop Tech Lead']);
		cy.contains('button', 'Save').should('be.enabled');
	});

	it('allows shop techs to save schedule edits', () => {
		mountEditor(['Shop Tech']);
		cy.contains('button', 'Save').should('be.enabled');
	});

	it('submits the timestamp the calendar data was received', () => {
		cy.intercept('POST', '**/techs/forecast/override', {
			body: { status: 'ok' }
		}).as('save');
		mountEditor(['Shop Tech Lead'], '2025-01-15T12:00:00.000Z');

		cy.contains('button', 'Save').click();
		cy.wait('@save').its('request.body.received_at').should('eq', '2025-01-15T12:00:00.000Z');
	});
});
