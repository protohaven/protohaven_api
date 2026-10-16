import Profile from './profile.svelte';

const baseProfile = {
	fullname: 'Ada Lovelace',
	bio: 'Mathematician',
	email_status: 'OK',
	active_membership: 'OK',
	capabilities_listed: 'OK',
	paperwork: 'OK',
	discord_user: 'OK'
};

describe('instructor profile', () => {
	it('does not show the incomplete warning when fully onboarded', () => {
		cy.mount(Profile, { props: { profile: Promise.resolve(baseProfile) } });
		cy.contains('Your status is incomplete').should('not.exist');
	});

	it('shows the incomplete warning when onboarding data is missing', () => {
		cy.mount(Profile, {
			props: {
				profile: Promise.resolve({
					...baseProfile,
					paperwork: 'missing'
				})
			}
		});
		cy.contains('Your status is incomplete').should('be.visible');
	});
});
