import InstructorList from './instructor_list.svelte';
import type { InstructorListData } from './types';

function mountList(data: InstructorListData) {
	cy.mount(InstructorList, {
		props: {
			visible: true,
			admin: true,
			data,
			onEnrollmentChanged: () => undefined
		}
	});
}

const data: InstructorListData = {
	enrollment_map: {
		'neon-bob': 'Bob Incomplete',
		'neon-carol': 'Carol Complete',
		ghost: 'Ghost Enrolled'
	},
	capabilities: [
		{
			id: 'cap-alice',
			name: 'Alice Missing Neon',
			email: 'alice@example.com',
			neon_id: null,
			active: true,
			classes: {},
			clearances: []
		},
		{
			id: 'cap-bob',
			name: 'Bob Incomplete',
			email: 'bob@example.com',
			neon_id: 'neon-bob',
			active: true,
			w9: '',
			direct_deposit: '',
			bio: '',
			profile_pic: '',
			classes: {},
			clearances: []
		},
		{
			id: 'cap-carol',
			name: 'Carol Complete',
			email: 'carol@example.com',
			neon_id: 'neon-carol',
			active: true,
			w9: 'w9-file',
			direct_deposit: 'dd-file',
			bio: 'A bio',
			profile_pic: 'pic-url',
			classes: {},
			clearances: []
		}
	]
};

describe('instructor roster', () => {
	it('highlights instructors missing a Neon account or enrollment', () => {
		mountList(data);

		cy.contains('.alert-danger', 'Alice Missing Neon').should('be.visible');
		cy.contains('.alert-warning', 'Ghost Enrolled').should('be.visible');
		cy.contains('tr', 'Alice Missing Neon').should('have.class', 'table-warning');
	});

	it('shows missing paperwork badges and roster links', () => {
		mountList(data);

		cy.contains('tr', 'Bob Incomplete').within(() => {
			cy.contains('No W9').should('be.visible');
			cy.contains('No DD').should('be.visible');
			cy.contains('No pic/bio').should('be.visible');
		});

		cy.contains('tr', 'Carol Complete').within(() => {
			cy.contains('No W9').should('not.exist');
			cy.contains('No DD').should('not.exist');
			cy.contains('No pic/bio').should('not.exist');
			cy.contains('View Page').should('have.attr', 'href', '/instructor?email=carol%40example.com');
			cy.contains('Neon CRM').should(
				'have.attr',
				'href',
				'https://protohaven.app.neoncrm.com/admin/accounts/neon-carol'
			);
		});
	});
});
