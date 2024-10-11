import { get_ph_events, ph_events_to_elems } from './lib';
import { useEffect, useState } from '@wordpress/element';
import { createRoot } from 'react-dom/client';

function App( { attributes } ) {
	const maxClassesShown = parseInt(attributes.maxClassesShown);
	const [state, setState] = useState([]);

	useEffect(() => {
		get_ph_events(maxClassesShown).then((events) => {
			events.splice(maxClassesShown);
			setState(events);
		});
	}, [maxClassesShown]);
  return (
    <>
      { ph_events_to_elems(state) }
    </>
  );
}

window.addEventListener("load", (event) => {
	const elem = document.getElementById("protohaven-class-ticker");
	const root = createRoot(elem);
	root.render(<App attributes={elem.dataset}/>);
});
