import MemberAgreement from './member_agreement.svelte';

describe('MemberAgreement', () => {
	it('disables submission while checking', () => {
		cy.mount(MemberAgreement, {
			props: {
				on_submit: cy.stub().as('on_submit'),
				checking: true
			}
		});

		cy.contains(
			'button',
			'I have read and understand this agreement and agree to be bound by its requirements.'
		).should('be.disabled');
	});

	it('submits when not checking', () => {
		cy.mount(MemberAgreement, {
			props: {
				on_submit: cy.stub().as('on_submit'),
				checking: false
			}
		});

		cy.contains(
			'button',
			'I have read and understand this agreement and agree to be bound by its requirements.'
		).click();
		cy.get('@on_submit').should('have.been.calledOnce');
	});
});
