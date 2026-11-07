import Attendance from './attendance.svelte';

describe('techs attendance', () => {
	it('is not shown when the attendance tab is hidden', () => {
		cy.mount(Attendance, { props: { visible: false } });

		cy.contains('Tech Attendance').should('not.exist');
	});

	it('runs an attendance report over the selected time period', () => {
		cy.intercept('POST', '**/techs/attendance_report', {
			body: {
				header: ['Date', 'Shift', 'Name'],
				rows: [['2025-01-01', 'AM', 'Ada Lovelace']]
			}
		}).as('report');

		cy.mount(Attendance, { props: { visible: true } });

		cy.get('input[placeholder="From Date"]').clear().type('2025-01-01');
		cy.get('input[placeholder="To Date"]').clear().type('2025-01-07');
		cy.contains('button', 'Generate Report').click();

		cy.wait('@report').then((interception) => {
			expect(interception.request.body).to.deep.equal({
				start_date: '2025-01-01',
				end_date: '2025-01-07'
			});
		});

		cy.contains('Ada Lovelace').should('be.visible');
		cy.contains('th', 'Shift').should('be.visible');
	});
});
