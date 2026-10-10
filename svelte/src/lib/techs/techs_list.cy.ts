import TechsList from './techs_list.svelte';

const ada = {
	neon_id: '1',
	name: 'Ada Lovelace',
	email: 'ada@example.com',
	clearances: ['Woodshop'],
	shop_tech_shift: ['Sun', 'AM'],
	shop_tech_first_day: '2024-01-01',
	shop_tech_last_day: '2025-01-01',
	area_lead: 'Woodshop',
	interest: 'CNC',
	expertise: 'Welding',
	volunteer_bio: 'Mathematician and proto-shop-tech.',
	volunteer_picture: 'https://example.com/ada.jpg'
};

const grace = {
	neon_id: '2',
	name: 'Grace Hopper',
	email: 'grace@example.com',
	clearances: ['Woodshop', 'Metal Shop', 'Lathe'],
	shop_tech_shift: ['Mon', 'PM'],
	shop_tech_first_day: '2024-02-01',
	shop_tech_last_day: '2025-02-01',
	area_lead: 'Metal Shop',
	interest: 'CNC',
	expertise: 'Programming'
};

function mountTechsList(overrides: Record<string, unknown> = {}) {
	cy.intercept('GET', '**/techs/list', {
		body: { techs: [ada, grace], tech_lead: false, ...overrides }
	}).as('techs');

	cy.mount(TechsList, {
		props: {
			visible: true,
			user: null
		}
	});
	cy.wait('@techs');
}

function cardTitles() {
	return cy
		.get('.card .card-title')
		.then((els) => [...els].map((el) => el.textContent || '').filter((t) => t !== 'Tech Roster'));
}

describe('techs roster', () => {
	it('is not shown when the tab is not active', () => {
		cy.mount(TechsList, {
			props: {
				visible: false,
				user: null
			}
		});

		cy.contains('Tech Roster').should('not.exist');
	});

	it('shows clearances and sorts by name and clearances', () => {
		mountTechsList();

		cardTitles().should((titles) => {
			expect(titles[0]).to.include('Ada Lovelace');
			expect(titles[1]).to.include('Grace Hopper');
		});
		cy.contains('button', '1 Clearance(s)').should('be.visible');
		cy.contains('button', '3 Clearance(s)').should('be.visible');

		cy.contains('button', 'Sort').click();
		cy.contains('Most Clearances').click();
		cardTitles().should((titles) => {
			expect(titles[0]).to.include('Grace Hopper');
			expect(titles[1]).to.include('Ada Lovelace');
		});

		cy.contains('button', 'Sort').click();
		cy.contains('Least Clearances').click();
		cardTitles().should((titles) => {
			expect(titles[0]).to.include('Ada Lovelace');
			expect(titles[1]).to.include('Grace Hopper');
		});
	});

	it('shows tech photos and bios', () => {
		mountTechsList();

		cy.get('img[alt="Profile picture of Ada Lovelace"]').should(
			'have.attr',
			'src',
			'https://example.com/ada.jpg'
		);
		cy.contains('Mathematician and proto-shop-tech.').should('be.visible');
	});

	it('disenrolls a tech after confirmation', () => {
		cy.intercept('POST', '**/techs/enroll', { body: { status: 'ok' } }).as('enroll');
		cy.stub(window, 'confirm').returns(true);
		mountTechsList({ tech_lead: true });

		cy.contains('button', 'Disenroll').first().click();
		cy.wait('@enroll').then((interception) => {
			expect(interception.request.body).to.deep.include({
				neon_id: '1',
				enroll: false
			});
		});
	});

	it('enrolls a tech found via Neon search', () => {
		cy.intercept('POST', '**/neon_lookup*', {
			body: [{ neon_id: '99', name: 'Alan Turing', email: 'alan@example.com' }]
		}).as('lookup');
		cy.intercept('POST', '**/techs/enroll', { body: { status: 'ok' } }).as('enroll');
		mountTechsList({ tech_lead: true });

		cy.get('input[aria-label="Search Neon accounts by name or email"]').type('Alan');
		cy.wait('@lookup');
		cy.contains('Alan Turing (alan@example.com)').click();
		cy.contains('button', 'Enroll').click();
		cy.wait('@enroll').then((interception) => {
			expect(interception.request.body).to.deep.include({
				neon_id: '99',
				name: 'Alan Turing',
				email: 'alan@example.com',
				enroll: true
			});
		});
	});

	it('enrolls and creates a new member', () => {
		cy.intercept('POST', '**/neon_lookup*', {
			body: [{ neon_id: '88', name: 'Katherine Johnson', email: 'katherine@example.com' }]
		}).as('lookup');
		cy.intercept('POST', '**/techs/enroll', { body: { status: 'ok' } }).as('enroll');
		mountTechsList({ tech_lead: true });

		cy.get('input[aria-label="Search Neon accounts by name or email"]').type('Katherine');
		cy.wait('@lookup');
		cy.contains('+ Create New (Neon CRM)').click();

		cy.get('input[aria-label="Full name for new account"]').type('Katherine Johnson');
		cy.get('input[aria-label="Email address for new account"]').type('katherine@example.com');
		cy.contains('button', 'Create & Enroll').click();
		cy.wait('@enroll').then((interception) => {
			expect(interception.request.body).to.deep.include({
				neon_id: null,
				name: 'Katherine Johnson',
				email: 'katherine@example.com',
				enroll: true,
				create_account: true
			});
		});
	});
});
