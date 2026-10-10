import Storage from './storage.svelte';

interface FakeSocket {
	addEventListener(type: string, cb: (e: { data?: string }) => void): void;
	close(): void;
	emit(type: string, data?: string): void;
}

function makeFakeSocket(): FakeSocket {
	const listeners: Record<string, ((e: { data?: string }) => void)[]> = {};
	return {
		addEventListener(type, cb) {
			(listeners[type] ||= []).push(cb);
		},
		close() {
			(listeners['close'] || []).forEach((cb) => cb({}));
		},
		emit(type, data) {
			(listeners[type] || []).forEach((cb) => cb({ data }));
		}
	};
}

function stubWebSocket(): { socket: FakeSocket } {
	const holder: { socket: FakeSocket } = { socket: makeFakeSocket() };
	cy.window().then((win) => {
		win.WebSocket = function FakeWebSocket() {
			return holder.socket;
		} as unknown as typeof WebSocket;
	});
	return holder;
}

function mountStorage() {
	cy.mount(Storage, { props: { visible: true } });
}

function squareSub(overrides: Record<string, unknown> = {}) {
	return {
		id: '111',
		status: 'ACTIVE',
		created_at: '2025-01-29T15:18:13-05:00',
		start_date: '2025-01-29',
		charged_through_date: '2025-08-29',
		monthly_billing_anchor_date: 29,
		customer: 'Ada Lovelace',
		plan: 'Test Plan',
		price: 5000,
		membership_status: 'Active',
		note: JSON.stringify({
			storage_type: 'Cart',
			storage_id: 'L12',
			storage_detail: 'by the window'
		}),
		unpaid: [],
		...overrides
	};
}

describe('techs storage', () => {
	it('looks up a Neon ID by name or email', () => {
		cy.intercept('POST', '**/neon_lookup*', {
			body: [{ display: 'Ada Lovelace (ada@example.com)' }]
		}).as('lookup');

		mountStorage();

		cy.get('input[type="text"]').type('Ada');
		cy.contains('button', 'Search').click();
		cy.wait('@lookup').its('request.url').should('include', 'search=Ada');
		cy.contains('Ada Lovelace (ada@example.com)').should('be.visible');
	});

	it('shows active subscriptions but no email or unpaid invoices for non-leads', () => {
		const { socket } = stubWebSocket();
		mountStorage();

		cy.window().then(() => {
			socket.emit('message', JSON.stringify(squareSub()));
			socket.close();
		});

		cy.contains('Ada Lovelace').should('be.visible');
		cy.contains('Test Plan').should('be.visible');
		cy.contains('Active').should('be.visible');
		cy.contains('th', 'Email').should('not.exist');
		cy.contains('.badge', '0').should('not.exist');
	});

	it('does not render subscription data when the websocket reports permission denied', () => {
		cy.stub(window, 'alert').as('alert');
		const { socket } = stubWebSocket();
		mountStorage();

		cy.window().then(() => {
			socket.emit('message', JSON.stringify({ error: 'permission denied' }));
			socket.close();
		});

		cy.get('@alert').should('have.been.calledWith', 'permission denied');
		cy.get('tbody tr').should('have.length', 0);
	});

	it('renders unpaid invoice badges that link to Square invoices', () => {
		const { socket } = stubWebSocket();
		mountStorage();

		cy.window().then(() => {
			socket.emit(
				'message',
				JSON.stringify(squareSub({ email: 'ada@example.com', unpaid: ['001'] }))
			);
			socket.close();
		});

		cy.contains('th', 'Email').should('be.visible');
		cy.get('#sub0').should('contain', '1').click();
		cy.contains('a', '001').should(
			'have.attr',
			'href',
			'https://app.squareup.com/dashboard/invoices/001'
		);
	});

	it('edits subscription type, id, and note and saves changes', () => {
		cy.intercept('POST', '**/techs/storage_subscriptions/111/note', {
			body: { status: 'ok' }
		}).as('note');
		const { socket } = stubWebSocket();
		mountStorage();

		cy.window().then(() => {
			socket.emit('message', JSON.stringify(squareSub()));
			socket.close();
		});

		// Change the storage type using the dropdown.
		cy.contains('button', 'Cart').click();
		cy.contains('Locker').click();
		cy.wait('@note').then((interception) => {
			expect(interception.request.body.note).to.contain('"storage_type":"Locker"');
		});

		// Edit the storage ID through the editable cell.
		cy.get('tbody tr').first().find('button[aria-label="Edit null"]').first().click();
		cy.get('tbody tr').first().find('input[aria-label="Edit null"]').first().clear().type('L13');
		cy.get('tbody tr').first().find('[aria-label="Save changes"]').filter(':visible').click();
		cy.wait('@note').then((interception) => {
			expect(interception.request.body.note).to.contain('"storage_id":"L13"');
		});
	});

	it('shows Airtable-based subscriptions with the Airtable help link', () => {
		const { socket } = stubWebSocket();
		mountStorage();

		cy.window().then(() => {
			socket.emit(
				'message',
				JSON.stringify(
					squareSub({
						id: 'airtable-1',
						plan: 'Non-Square Agreement',
						note: JSON.stringify({
							storage_type: 'Cage',
							storage_id: 'C3',
							storage_detail: 'top row'
						})
					})
				)
			);
			socket.close();
		});

		cy.contains('Non-Square Agreement').should('be.visible');
		cy.get('a[href*="airtable.com/appZIwlIgaq1Ps28Y"]')
			.should('have.attr', 'target', '_blank')
			.and('be.visible');
		// Airtable agreements are edited on Airtable, so their dropdown items are disabled.
		cy.contains('button', 'Cage').click();
		cy.contains('Locker').should('have.class', 'disabled');
	});
});
