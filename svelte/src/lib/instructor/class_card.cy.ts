import ClassCard from './class_card.svelte';

function mountClassCard(props: Record<string, unknown> = {}, attendees: unknown[] = []) {
	cy.intercept('GET', '**/instructor/class/attendees*', { body: attendees }).as('attendees');
	cy.intercept('GET', '**/instructor/class/neon_state*', {
		body: { publishEvent: true, archived: false }
	}).as('neonState');

	const base = {
		schedule_id: 'sched-1',
		c_init: {
			event_id: '111',
			name: 'Intro to Woodshop',
			sessions: [['2025-01-15T18:00:00-05:00', '2025-01-15T21:00:00-05:00']] as [string, string][],
			capacity: 6,
			supply_state: 'Supplies Confirmed',
			volunteer: false,
			clearances: [],
			prefill: 'https://example.com/log'
		},
		submissions: null
	};

	const merged = { ...base, ...props };
	if (props.c_init) {
		merged.c_init = { ...base.c_init, ...(props.c_init as Record<string, unknown>) };
	}

	cy.mount(ClassCard, { props: merged });
	cy.wait('@attendees');
	cy.wait('@neonState');
}

function mountProposedClass(props: Record<string, unknown> = {}) {
	const base = {
		schedule_id: 'sched-1',
		c_init: {
			event_id: null,
			name: 'Proposed Class',
			sessions: [['2025-01-20T18:00:00-05:00', '2025-01-20T21:00:00-05:00']] as [string, string][],
			capacity: 6,
			supply_state: 'Supplies Confirmed',
			volunteer: false,
			clearances: [],
			prefill: 'https://example.com/log'
		},
		submissions: null
	};

	cy.mount(ClassCard, { props: { ...base, ...props } });
}

const SCHEDULED_RESPONSE = {
	event_id: '111',
	name: 'Intro to Woodshop',
	sessions: [['2025-01-15T18:00:00-05:00', '2025-01-15T21:00:00-05:00']],
	capacity: 6,
	supply_state: 'Supplies Confirmed',
	volunteer: false,
	confirmed: null,
	clearances: [],
	prefill: 'https://example.com/log',
	rejected: false
};

const PROPOSED_RESPONSE = {
	...SCHEDULED_RESPONSE,
	event_id: null,
	name: 'Proposed Class',
	sessions: [['2025-01-20T18:00:00-05:00', '2025-01-20T21:00:00-05:00']],
	rejected: true
};

describe('instructor class card', () => {
	it('indicates when a log has not yet been submitted', () => {
		mountClassCard();
		cy.contains('Not Yet Logged').should('be.visible');
		cy.contains('No log submissions yet').should('be.visible');
	});

	it('indicates when a log has been submitted', () => {
		mountClassCard({
			submissions: { '111': ['2025-01-16T10:00:00-05:00'] }
		});
		cy.contains('Logged').should('be.visible');
		cy.contains('No log submissions yet').should('not.exist');
	});

	it('posts a cancel request for the scheduled class', () => {
		cy.intercept('POST', '**/instructor/class/cancel', {
			body: {
				event_id: '111',
				name: 'Intro to Woodshop',
				sessions: [['2025-01-15T18:00:00-05:00', '2025-01-15T21:00:00-05:00']],
				capacity: 6,
				supply_state: 'Supplies Confirmed',
				volunteer: false,
				confirmed: null,
				clearances: [],
				prefill: 'https://example.com/log',
				rejected: true
			}
		}).as('cancel');

		mountClassCard();
		cy.contains('button', 'Actions').click();
		cy.contains('Cancel class (requires no attendees)').click();

		cy.wait('@cancel').then((interception) => {
			expect(interception.request.body).to.deep.equal({ class_id: 'sched-1' });
		});
	});

	it('marks a proposed class unavailable without posting to Neon', () => {
		cy.intercept('POST', '**/instructor/class/update', {
			body: PROPOSED_RESPONSE
		}).as('update');

		mountProposedClass();
		cy.contains('button', 'Actions').click();
		cy.contains('Mark unavailable (hides permanently)').click();

		cy.wait('@update').then((interception) => {
			expect(interception.request.body).to.deep.equal({ eid: 'sched-1', pub: false });
		});
	});

	it('switches a paid class to volunteer', () => {
		cy.intercept('POST', '**/instructor/class/volunteer', {
			body: { ...SCHEDULED_RESPONSE, volunteer: true }
		}).as('volunteer');

		mountClassCard();
		cy.contains('button', 'Actions').click();
		cy.contains('Volunteer').click();
		cy.wait('@volunteer').then((interception) => {
			expect(interception.request.body).to.deep.equal({
				eid: 'sched-1',
				volunteer: true
			});
		});
	});

	it('switches a volunteer class back to paid', () => {
		cy.intercept('POST', '**/instructor/class/volunteer', {
			body: { ...SCHEDULED_RESPONSE, volunteer: false }
		}).as('paid');

		mountClassCard({ c_init: { event_id: '111', volunteer: true } });
		cy.contains('button', 'Actions').click();
		cy.contains('Switch to Paid').click();
		cy.wait('@paid').then((interception) => {
			expect(interception.request.body).to.deep.equal({
				eid: 'sched-1',
				volunteer: false
			});
		});
	});

	it('marks supplies as needed', () => {
		cy.intercept('POST', '**/instructor/class/supply_req', {
			body: { ...SCHEDULED_RESPONSE, supply_state: 'Supplies Requested' }
		}).as('supplyNeeded');

		mountClassCard();
		cy.contains('button', 'Actions').click();
		cy.contains('Supplies needed').click();
		cy.wait('@supplyNeeded').then((interception) => {
			expect(interception.request.body).to.deep.equal({
				eid: 'sched-1',
				missing: true
			});
		});
	});

	it('marks supplies as OK', () => {
		cy.intercept('POST', '**/instructor/class/supply_req', {
			body: SCHEDULED_RESPONSE
		}).as('supplyOk');

		mountClassCard({
			c_init: { event_id: '111', supply_state: 'Supplies Requested' }
		});
		cy.contains('button', 'Actions').click();
		cy.contains('Supplies OK').click();
		cy.wait('@supplyOk').then((interception) => {
			expect(interception.request.body).to.deep.equal({
				eid: 'sched-1',
				missing: false
			});
		});
	});

	it('renders attendee names, emails, and registration dates', () => {
		mountClassCard({}, [
			{
				name: 'John Doe',
				email: 'john@example.com',
				registration_status: 'SUCCEEDED',
				registration_date: '2025-01-15'
			}
		]);

		cy.contains('John Doe (john@example.com)').should('be.visible');
		cy.contains('registered 2025-01-15').should('be.visible');
	});

	it('opens the pre-filled log form with attendee names and clearances', () => {
		cy.window().then((win) => {
			cy.stub(win, 'open').as('windowOpen');
		});

		mountClassCard(
			{
				c_init: {
					event_id: '111',
					clearances: ['Woodshop'],
					prefill: 'https://example.com/log?attendees=ATTENDEE_NAMES'
				}
			},
			[
				{
					name: 'John Doe',
					email: 'john@example.com',
					registration_status: 'SUCCEEDED',
					registration_date: '2025-01-15'
				}
			]
		);

		cy.contains('Clearances earned').should('be.visible');
		cy.contains('Woodshop').should('be.visible');

		cy.contains('button', 'Actions').click();
		cy.contains('Submit Log').click();

		cy.get('@windowOpen').should(
			'be.calledWith',
			'https://example.com/log?attendees=John%20Doe%20(john%40example.com)',
			'_blank'
		);
	});
});
