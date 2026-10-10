import { defineConfig } from 'cypress';

export default defineConfig({
	component: {
		devServer: {
			framework: 'svelte',
			bundler: 'vite',
			viteConfig: async () => (await import('./cypress.vite.config')).default
		},
		indexHtmlFile: 'cypress/support/component-index.html',
		specPattern: 'src/**/*.cy.ts',
		supportFile: 'cypress/support/component.ts'
	}
});
