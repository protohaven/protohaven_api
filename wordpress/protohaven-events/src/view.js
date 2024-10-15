import { App } from './app';
import { createRoot } from 'react-dom/client';

window.addEventListener("load", (event) => {
	const elem = document.getElementById("protohaven-events");
	const data = JSON.parse(elem.children[0].innerHTML);
	const root = createRoot(elem);
	root.render(<App initialData={data} {...elem.dataset} />);
});
