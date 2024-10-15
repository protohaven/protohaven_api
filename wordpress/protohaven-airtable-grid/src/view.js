import { get_ph_data, render_grid } from './lib';
import { useEffect, useState } from '@wordpress/element';
import { createRoot } from 'react-dom/client';

function App( { attributes } ) {
	console.log("Attribs", attributes);
	const [state, setState] = useState([]);

	useEffect(() => {
		const { token, base, table } = attributes;
		get_ph_data(token, base, table).then(setState);
	}, []);
  	return render_grid(state, attributes);
}

window.addEventListener("load", (event) => {
	const elem = document.getElementById("protohaven-airtable-grid");
	const root = createRoot(elem);
	root.render(<App attributes={elem.dataset}/>);
});
