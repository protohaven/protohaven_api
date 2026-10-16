import Shifts from './shifts.svelte';

function localToday() {
	const now = new Date();
	const mm = (now.getMonth() + 1).toString().padStart(2, '0');
	const dd = now.getDate().toString().padStart(2, '0');
	return `${now.getFullYear()}-${mm}-${dd}`;
}

function mountShifts(calendarView: Record<string, unknown>[]) {
	cy.intercept('GET', '**/techs/forecast*', {
		body: { calendar_view: calendarView }
	}).as('forecast');
	cy.intercept('GET', '**/techs/list', {
		body: { techs: [{ name: 'Ada Lovelace', shift: 'Sun AM' }] }
	}).as('techs');

	cy.mount(Shifts, {
		props: {
			visible: true,
			user: {
				fullname: 'Ada Lovelace',
				email: 'ada@example.com',
				roles: ['Tech Lead']
			}
		}
	});
	cy.wait('@forecast');
}

describe('techs shifts', () => {
	it('loads the calendar and opens the override editor when a shift is clicked', () => {
		mountShifts([
			{
				date: '2025-01-05',
				AM: {
					id: 'am-1',
					color: 'success',
					people: ['Ada Lovelace'],
					ovr: {
						id: 'ovr-1',
						orig: ['Grace Hopper'],
						editor: 'Ada Lovelace'
					}
				},
				PM: { people: [] }
			}
		]);

		cy.contains('button', 'Ada Lovelace').click();
		cy.contains('Current shift:').should('be.visible');
		cy.contains('button', 'Revert').should('be.visible');
	});

	it('reverts an override and refreshes the calendar', () => {
		cy.intercept('DELETE', '**/techs/forecast/override', { body: { status: 'ok' } }).as('revert');
		mountShifts([
			{
				date: '2025-01-05',
				AM: {
					id: 'am-1',
					color: 'warning',
					people: ['Ada Lovelace'],
					ovr: {
						id: 'ovr-1',
						orig: ['Grace Hopper'],
						editor: 'Ada Lovelace'
					}
				},
				PM: { people: [] }
			}
		]);

		cy.contains('button', 'Ada Lovelace').click();
		cy.contains('button', 'Revert').click();
		cy.wait('@revert');
		cy.wait('@forecast');
	});

	it('highlights the current day', () => {
		const today = localToday();
		mountShifts([
			{
				date: today,
				AM: { people: [] },
				PM: { people: [] }
			}
		]);

		cy.get('.day.today').should('contain', today);
	});
});
