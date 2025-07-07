import { sveltekit } from '@sveltejs/kit/vite';
import { svelte } from '@sveltejs/vite-plugin-svelte'
import { defineConfig } from 'vitest/config';

// Base URL of the flask backend server
const SERVER_BASE = 'http://flask:5000';
const WS_SERVER_BASE = 'ws://flask:5000';

// Paths to proxy to the backend.
// See https://vitejs.dev/config/server-options#server-proxy
const PROXY_PATHS = [
  '^/instructor/.',
  '^/techs/.',
  '^/member/.',
  '^/staff/.',
  '^/events/.',
  '^/instructor/.',
  '^/admin/.',
  '/whoami',
  '/neon_lookup',
  '/class_listing',
  '/welcome/announcement_ack',
];
const WS_PROXY_PATHS = [
  '/welcome/ws',
  '/staff/summarize_discord',
];
let proxy = {};
for (let p of PROXY_PATHS) {
  proxy[p] = SERVER_BASE;
}
for (let p of WS_PROXY_PATHS) {
  proxy[p] = {
    target: WS_SERVER_BASE,
    changeOrigin: true,
    ws: true,
  };
}
console.log("Proxying endpoints to flask backend server:", proxy);

export default defineConfig({
	plugins: [sveltekit()],//[svelte()], // [sveltekit()] previously, but didn't work with Cypress
	test: {
	 	include: ['src/**/*.{test,spec}.{js,ts}']
	},
  server: { proxy },
});
