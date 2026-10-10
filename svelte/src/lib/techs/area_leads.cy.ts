import AreaLeads from './area_leads.svelte';

const areaLeads = {
	area_leads: {
		Woodshop: [{ name: 'Ada Lovelace', email: 'ada@example.com', shift: ['Sun', 'AM'] }],
		'Metal Shop': []
	},
	other_leads: {
		'Extra Area': [{ name: 'Grace Hopper', email: 'grace@example.com', shift: ['Mon', 'PM'] }]
	}
};

describe('techs area leads', () => {
	it('is hidden when not visible', () => {
		cy.mount(AreaLeads, { props: { visible: false } });
		cy.contains('Areas & Leads').should('not.exist');
	});

	it('shows assigned leads and additional contacts', () => {
		cy.intercept('GET', '**/techs/area_leads', { body: areaLeads }).as('areaLeads');

		cy.mount(AreaLeads, { props: { visible: true } });
		cy.wait('@areaLeads');

		cy.contains('Woodshop').should('be.visible');
		cy.contains('Ada Lovelace').should('be.visible');
		cy.contains('ada@example.com').should('be.visible');
		cy.contains('Shift: Sun AM').should('be.visible');
		cy.contains('Additional Contacts').should('be.visible');
		cy.contains('Extra Area').should('be.visible');
		cy.contains('Grace Hopper').should('be.visible');
	});
});
