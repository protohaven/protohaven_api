import { get_ph_data, render_grid } from './lib';
import { useEffect, useState } from '@wordpress/element';
import { createRoot } from 'react-dom/client';

function App( { initialData, attributes } ) {
	const [state, setState] = useState(initialData);
  	return render_grid(state, attributes);
}

window.addEventListener("load", (event) => {
	for (let elem of document.getElementsByClassName("protohaven-airtable-grid")) {
		const root = createRoot(elem);
		const data = JSON.parse(elem.children[0].innerHTML)['records'] || [];
		root.render(<App initialData={data} attributes={elem.dataset}/>);
	}
});
