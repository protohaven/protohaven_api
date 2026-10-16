import WrongTime from './wrong_time.svelte';

describe('WrongTime', () => {
	it('shows membership details and delegates actions', () => {
		cy.mount(WrongTime, {
			props: {
				on_continue: cy.stub().as('on_continue'),
				on_close: cy.stub().as('on_close'),
				name: 'Ada Lovelace',
				membership_window: 'Mon-Fri 9am-9pm'
			}
		});

		cy.contains('Heads up, Ada Lovelace.').should('be.visible');
		cy.contains('Mon-Fri 9am-9pm').should('be.visible');

		cy.contains('button', 'Sign in anyway').click();
		cy.get('@on_continue').should('have.been.calledOnce');

		cy.contains('button', 'Go back').click();
		cy.get('@on_close').should('have.been.calledOnce');
	});
});
