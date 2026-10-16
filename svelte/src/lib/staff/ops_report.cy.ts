import OpsReport from './ops_report.svelte';

describe('staff ops report', () => {
	it('renders metrics received over the ops summary websocket', () => {
		let ws: {
			onmessage: (m: { data: string }) => void;
			onerror: (e: Event) => void;
			onclose: () => void;
		};

		cy.window().then((win) => {
			ws = {} as typeof ws;
			win.WebSocket = function FakeWebSocket() {
				return ws;
			} as unknown as typeof WebSocket;
		});

		cy.mount(OpsReport, { props: { visible: true } });

		cy.window().then(() => {
			ws.onmessage({
				data: JSON.stringify({
					category: 'Facilities',
					label: 'Front door locked',
					total: 1,
					index: 1,
					value: 'Locked',
					target: 'Locked',
					url: 'https://example.com/source',
					source: 'Door API',
					timescale: 'now'
				})
			});
			ws.onclose();
		});

		cy.contains('FACILITIES').should('be.visible');
		cy.contains('Front door locked').should('be.visible');
		cy.contains('Locked').should('be.visible');
		cy.contains('Door API').should('be.visible');
		cy.contains('now').should('be.visible');
	});
});
