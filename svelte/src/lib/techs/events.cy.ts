import Events from './events.svelte';

const adminEvent = {
	id: '111',
	name: '(SHOP TECH ONLY) Lathe Basics',
	start: '2025-01-15T18:00:00-05:00',
	capacity: 6,
	attendee_count: 1,
	attendees: [123],
	attendee_emails: ['ada@example.com'],
	ticket_id: 'ticket-1',
	attendee_details: [
		{
			name: 'Ada Lovelace',
			email: 'ada@example.com',
			phone: '(412) 555-0100'
		}
	]
};

function mountEvents() {
	cy.intercept('GET', '**/techs/events', {
		body: {
			events: [adminEvent],
			can_register: true,
			can_edit: true,
			is_admin: true
		}
	}).as('events');

	cy.mount(Events, {
		props: {
			visible: true,
			user: { neon_id: 999, email: 'lead@example.com', fullname: 'Test Lead' }
		}
	});
	cy.wait('@events');
}

describe('techs events', () => {
	it('shows registrant name, email, and phone to admins', () => {
		mountEvents();

		cy.contains('Ada Lovelace').should('be.visible');
		cy.contains('Email: ada@example.com').should('be.visible');
		cy.contains('Phone: (412) 555-0100').should('be.visible');
	});

	it('hides registrant phone details from non-admins', () => {
		cy.intercept('GET', '**/techs/events', {
			body: {
				events: [
					{
						...adminEvent,
						attendee_details: [{ name: 'Ada Lovelace', email: 'ada@example.com' }]
					}
				],
				can_register: true,
				can_edit: false,
				is_admin: false
			}
		}).as('events');

		cy.mount(Events, {
			props: {
				visible: true,
				user: { neon_id: 123, email: 'tech@example.com', fullname: 'Shop Tech' }
			}
		});
		cy.wait('@events');

		cy.contains('Ada Lovelace').should('be.visible');
		cy.contains('Email: ada@example.com').should('be.visible');
		cy.contains('Phone:').should('not.exist');
	});

	it('does not show register controls when a generic shop tech cannot register', () => {
		cy.intercept('GET', '**/techs/events', {
			body: {
				events: [{ ...adminEvent, attendee_details: [] }],
				can_register: false,
				can_edit: false,
				is_admin: false
			}
		}).as('events');

		cy.mount(Events, {
			props: {
				visible: true,
				user: { neon_id: 123, email: 'shop@example.com', fullname: 'Generic Shop Tech' }
			}
		});
		cy.wait('@events');

		cy.contains('button', 'Register').should('not.exist');
		cy.contains('button', 'Unregister').should('not.exist');
	});

	it('allows admins to de-register an attendee by email', () => {
		cy.intercept('POST', '**/techs/event', {
			body: { status: 'ok' }
		}).as('eventPost');
		cy.stub(window, 'confirm').returns(true);

		mountEvents();

		cy.contains('button', 'De-register').click();
		cy.wait('@eventPost').then((interception) => {
			expect(interception.request.body).to.deep.include({
				event_id: '111',
				action: 'unregister',
				attendee_email: 'ada@example.com'
			});
		});
	});
});
