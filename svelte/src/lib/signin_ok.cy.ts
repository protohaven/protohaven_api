import SigninOk from './signin_ok.svelte';

const reservations = [
	{
		id: 'r1',
		is_signed_in_member: true,
		area: 'Woodshop',
		resource: 'Table Saw',
		start: '9:00 AM',
		end: '11:00 AM',
		name: 'Ada Lovelace'
	},
	{
		id: 'r2',
		is_signed_in_member: true,
		area: 'Woodshop',
		resource: 'Planer',
		start: '9:00 AM',
		end: '12:00 PM',
		name: 'Ada Lovelace'
	},
	{
		id: 'r3',
		is_signed_in_member: false,
		area: 'Metal Shop',
		resource: 'Mill',
		start: '8:00 AM',
		end: '10:00 AM',
		name: 'Grace Hopper'
	}
];

describe('signin_ok', () => {
	it("displays the day's reservations, including ones from earlier in the day", () => {
		cy.mount(SigninOk, {
			props: {
				on_close: cy.stub().as('on_close'),
				on_enroll: cy.stub().as('on_enroll'),
				name: 'Ada Lovelace',
				email: 'ada@example.com',
				reservations
			}
		});

		cy.contains("Today's Reservations:").should('be.visible');
		cy.contains('Your Reservations').should('be.visible');
		cy.contains('Other Reservations').should('be.visible');
		cy.contains('Table Saw (9:00 AM)').should('be.visible');
		cy.contains('Planer (9:00 AM)').should('be.visible');
		cy.contains('Mill (8:00 AM)').should('be.visible');
	});
});
