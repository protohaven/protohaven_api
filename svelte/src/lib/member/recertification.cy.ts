import Recertification from './recertification.svelte';

const rc = {
	pending: [
		['LTH', '2025-02-01', { tool_name: 'Metal Lathe', quiz_url: 'https://example.com/quiz' }],
		['MLL', '2024-01-01', { tool_name: 'Manual Mill', quiz_url: null }]
	],
	configs: [
		{
			tool: 'LTH',
			tool_name: 'Metal Lathe',
			humanized: 'Take the quiz',
			quiz_url: 'https://example.com/quiz'
		},
		{
			tool: 'MLL',
			tool_name: 'Manual Mill',
			humanized: 'See an instructor',
			quiz_url: null
		}
	]
};

describe('recertification card', () => {
	it('is not rendered when hidden', () => {
		cy.mount(Recertification, { props: { visible: false, rc } });

		cy.contains('Recertification').should('not.exist');
	});

	it('shows the wiki link and tools with recertification configured', () => {
		cy.mount(Recertification, { props: { visible: true, rc } });

		cy.contains('a', 'our wiki')
			.should('be.visible')
			.and(
				'have.attr',
				'href',
				'https://wiki.protohaven.org/books/policies/page/tool-recertification'
			);
		cy.contains('Metal Lathe').should('be.visible');
		cy.contains('Manual Mill').should('be.visible');
		cy.contains('Take the quiz').should('be.visible');
		cy.contains('See an instructor').should('be.visible');
	});
});
