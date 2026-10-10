import ClassCard from './class_card.svelte';

function mountClassCard(props: Record<string, unknown> = {}) {
	cy.intercept('GET', '**/instructor/class/attendees*', { body: [] }).as('attendees');
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

	cy.mount(ClassCard, { props: { ...base, ...props } });
	cy.wait('@attendees');
	cy.wait('@neonState');
}

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
});
