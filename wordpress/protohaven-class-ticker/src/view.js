import { ph_events_to_elems } from './lib';
import { useEffect, useState } from '@wordpress/element';
import { createRoot } from 'react-dom/client';

function App( { initialData, attributes } ) {
  const maxClassesShown = parseInt(attributes.maxClassesShown);
  const [state, setState] = useState(initialData.slice(0, maxClassesShown));
  return (
    <>
      { ph_events_to_elems(state) }
    </>
  );
}

window.addEventListener("load", (event) => {
	const elem = document.getElementById("protohaven-class-ticker");
	const root = createRoot(elem);
	const data = JSON.parse(elem.children[0].innerHTML) || [];
	root.render(<App initialData={data} attributes={elem.dataset}/>);
});
