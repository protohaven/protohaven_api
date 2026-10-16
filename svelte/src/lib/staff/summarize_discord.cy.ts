import SummarizeDiscord from './summarize_discord.svelte';

describe('staff discord summarizer', () => {
	it('requires a logged-in user', () => {
		cy.intercept('GET', '**/staff/discord_member_channels', { body: [] }).as('channels');
		cy.mount(SummarizeDiscord, {
			props: {
				visible: true,
				user: null
			}
		});
		cy.contains('You must be logged in to use this tool').should('be.visible');
	});

	it('summarizes selected channels and displays photos', () => {
		cy.intercept('GET', '**/staff/discord_member_channels', {
			body: ['#general']
		}).as('channels');

		let ws: {
			send: Cypress.Agent<sinon.SinonStub>;
			onopen: () => void;
			onmessage: (m: { data: string }) => void;
			onerror: (e: Event) => void;
			onclose: () => void;
		};

		cy.window().then((win) => {
			ws = { send: cy.stub() } as unknown as typeof ws;
			win.WebSocket = function FakeWebSocket() {
				return ws;
			} as unknown as typeof WebSocket;
		});

		cy.mount(SummarizeDiscord, {
			props: {
				visible: true,
				user: { fullname: 'Staff Person', email: 'staff@example.com' }
			}
		});
		cy.wait('@channels');
		cy.contains('label', '#general').should('be.visible');

		cy.contains('button', 'Submit').click();
		cy.window().then(() => {
			ws.onopen();
			ws.onmessage({
				data: JSON.stringify({
					type: 'individual',
					channel: '#general',
					created_at: '2025-01-01T10:00:00.000Z',
					author: 'Ada Lovelace',
					content: 'Hello Protohaven',
					images: ['https://example.com/photo.jpg'],
					videos: [],
					ref: 'https://discord.example/1'
				})
			});
			ws.onmessage({
				data: JSON.stringify({
					type: 'channel_summary',
					channel: '#general',
					content: 'Channel summary text'
				})
			});
			ws.onmessage({
				data: JSON.stringify({
					type: 'final_summary',
					content: '<p>Final summary text</p>'
				})
			});
			ws.onclose();
		});

		cy.contains('Channel summary text').should('be.visible');
		cy.contains('Final summary text').should('be.visible');
		cy.get('img[src="https://example.com/photo.jpg"]').should(
			'have.attr',
			'src',
			'https://example.com/photo.jpg'
		);
		cy.contains('.accordion-button', '#general').click();
		cy.contains('Hello Protohaven').should('be.visible');
	});
});
