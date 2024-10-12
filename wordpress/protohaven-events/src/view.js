import { App } from './lib';
import { createRoot } from 'react-dom/client';

window.addEventListener("load", (event) => {
	const elem = document.getElementById("protohaven-events");
	const root = createRoot(elem);
	root.render(<App {...elem.dataset} />);
});
