import ToolState from './tool_state.svelte';

const toolState = [
	{
		name: 'Band Saw',
		code: 'BS',
		status: 'Green (fully operational)',
		message: 'Running well',
		date: '2025-01-01',
		modified: 2,
		area: ['Woodshop']
	},
	{
		name: 'Drill Press',
		code: 'DP',
		status: 'Red (non-functional or unsafe)',
		message: 'Down for repairs',
		date: '2025-01-02',
		modified: 10,
		area: ['Metal Shop']
	}
];

const docsState = {
	by_code: {
		BS: {
			clearance: [
				{
					url: 'https://wiki.example.com/bandsaw-clearance',
					approved_revision: false,
					thresh: 2,
					approvals: { one: {} }
				}
			],
			tool_tutorial: [
				{
					url: 'https://wiki.example.com/bandsaw-tutorial',
					approved_revision: true,
					thresh: 0,
					approvals: {}
				}
			]
		},
		DP: {
			clearance_not_found_url: 'https://wiki.example.com/dp-clearance',
			tool_tutorial_not_found_url: 'https://wiki.example.com/dp-tutorial'
		}
	}
};

function mountToolState() {
	cy.intercept('GET', '**/techs/tool_state', { body: toolState }).as('toolState');
	cy.intercept('GET', '**/techs/docs_state', { body: docsState }).as('docsState');

	cy.mount(ToolState, {
		props: {
			visible: true
		}
	});
	cy.wait('@toolState');
	cy.wait('@docsState');
}

function toolHeaders() {
	return cy
		.get('.card .card-header')
		.then((els) =>
			[...els]
				.map((el) => el.textContent || '')
				.filter((t) => !t.includes('Tool Maintenance State'))
		);
}

describe('techs tool state', () => {
	it('loads tool state and shows a history link for each tool', () => {
		mountToolState();

		cy.contains('Band Saw').should('be.visible');
		cy.contains('Drill Press').should('be.visible');
		cy.get('a[href*="filter_Tool Name=Band Saw"]')
			.should('have.length', 1)
			.and('contain', 'history');
		cy.get('a[href*="filter_Tool Name=Drill Press"]')
			.should('have.length', 1)
			.and('contain', 'history');
	});

	it('shows guide and clearance documentation status with wiki links', () => {
		mountToolState();

		cy.contains('a', 'page missing 1 approval(s)')
			.should('be.visible')
			.and('have.attr', 'href', 'https://wiki.example.com/bandsaw-clearance');
		cy.contains('a', 'approved')
			.should('be.visible')
			.and('have.attr', 'href', 'https://wiki.example.com/bandsaw-tutorial');
		cy.contains('a', 'missing')
			.should('be.visible')
			.and('have.attr', 'href', 'https://wiki.example.com/dp-clearance');
	});

	it('sorts tools by name and urgency', () => {
		mountToolState();

		// Default urgency sort puts the red tool first.
		toolHeaders().should((headers) => {
			expect(headers[0]).to.include('Drill Press');
			expect(headers[1]).to.include('Band Saw');
		});

		cy.contains('button', 'Sort by Urgency (red/yellow/blue/green)').click();
		cy.contains('By Name').click();
		toolHeaders().should((headers) => {
			expect(headers[0]).to.include('Band Saw');
			expect(headers[1]).to.include('Drill Press');
		});
	});

	it('sorts tools by time in state', () => {
		mountToolState();

		cy.contains('button', 'Sort by Urgency (red/yellow/blue/green)').click();
		cy.contains('Longest time in State').click();
		toolHeaders().should((headers) => {
			expect(headers[0]).to.include('Drill Press');
			expect(headers[1]).to.include('Band Saw');
		});

		cy.contains('button', 'Sort by Longest time in State').click();
		cy.contains('Shortest time in State').click();
		toolHeaders().should((headers) => {
			expect(headers[0]).to.include('Band Saw');
			expect(headers[1]).to.include('Drill Press');
		});
	});

	it('filters tools by area', () => {
		mountToolState();

		cy.contains('button', 'Show All Areas').click();
		cy.contains('Metal Shop').click();
		cy.contains('Drill Press').should('be.visible');
		cy.contains('Band Saw').should('not.exist');
	});
});
