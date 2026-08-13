import { App } from './app';
import { createRoot } from 'react-dom/client';

window.addEventListener("load", (event) => {
	const elem = document.getElementById("protohaven-events");
	let data = {};
	try {
		data = JSON.parse(elem.children[0].innerHTML);
	} catch(e) {
		console.error(e);
	}
	const root = createRoot(elem);
	root.render(<App initialData={data} {...elem.dataset} />);
});
