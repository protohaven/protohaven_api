import { svelte } from '@sveltejs/vite-plugin-svelte';
import { fileURLToPath } from 'node:url';
import path from 'node:path';
import { defineConfig } from 'vite';

const dirname = path.dirname(fileURLToPath(import.meta.url));

export default defineConfig({
	plugins: [svelte()],
	resolve: {
		alias: {
			$lib: path.resolve(dirname, 'src/lib')
		}
	},
	css: {
		preprocessorOptions: {
			scss: {
				silenceDeprecations: [
					'legacy-js-api',
					'import',
					'global-builtin',
					'color-functions',
					'if-function'
				]
			}
		}
	}
});
