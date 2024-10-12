
import { useEffect, useState } from '@wordpress/element';

export function get_events(pagination) {
    let q_params = {
	rest_route: "/protohaven-events-plugin-api/v1/events",
        endDateAfter: new Date().toISOString().split('T')[0],
        publishedEvent: true,
        archived: false,
        ...pagination,
    };
    const queryString = new URLSearchParams(q_params).toString();
    return fetch('http://localhost:8080/?' + queryString).then(rep => rep.json());
}

function fetch_all_events(state, setState, cur=0, tot=1) {
	if (cur >= tot) {
		return;
	}
	console.log('get_events', cur, tot);
	get_events({currentPage: cur, pageSize: 50}).then((rep) => {
		console.log(rep);
		let newState = [...state, ...rep.events];
		setState(newState);
		// TODO finish
		// return fetch_all_events(newState, setState, cur+1, Math.min(rep.pagination.totalPages, 20));
	});
}

export function get_event_tickets(event_id) {
	return fetch(`http://localhost:8080/?rest_route=/protohaven-events-plugin-api/v1/event_tickets?neon_id=${event_id}`).then(rep => rep.json());
}

function gotoEvent(event_id){
	window.open('https://protohaven.app.neoncrm.com/np/clients/protohaven/event.jsp?event=' + event_id, '_blank').focus();
}

export function renderItem({id, title, area, shortDesc, level, features, price, discount, img, imgSize}) {
	let containerClass = "ph-item";
	if (img) {
		img = (<div class="ph-img">
			<h3>{area}{level ? " " + level : ""}</h3>
			<img src={img}/>
		</div>);
		containerClass += " cell";
	} else {
		img = <div class="ph-tag">{area} {level || ""}</div>;
		containerClass += " fullbleed";
	}
	features = [
		<div>Oct 10, 6-9pm (<a href="#">3 more</a>)</div>,
		<div>Ages 12+</div>,
		<div>3 hours</div>,
	];
	return (<div class={containerClass} id={id}>
		<div class="ph-content">
			{img}
			<	h3>{title}</h3>

			<div class="ph-desc">{shortDesc} (<a href="#">more</a>)</div>
		</div>
		<div class="ph-fold">
			<div class="ph-features">{features}</div>
			<button class="ph-footer">
				<div class="ph-price">$102</div>
				<div class="ph-discount">($75 for members)</div>
			</button>
		</div>
	</div>);
}


function extraFromName(name) {
	// Regex captures area, level, name, and optional paren suffix e.g.
	// Graphics 111: Printed Mugs (Dye Sublimation Clearance)
	// Graphics 111: Printed Mugs
	const regex = /^(\w+)\s+(\d+):\s+(.+?)(?:\s+\((.+)\))?$/;
	const m = name.match(regex);
	if (!m) {
		return null;
	}
	return {area: m[1], level: m[2], shortName: m[3]};
}

function imgFromDesc(desc) {
	let doc = document.createElement('div');
	doc.innerHTML = desc;
	let img = doc.getElementsByTagName('img');
	return (img.length !== 0) ? img[0].src : null;
}



function trunc(inputStr, maxLength) {
    let truncatedStr = '';
    const sentences = inputStr.split(/(?<=[.!?])\s+/);
    for (const sentence of sentences) {
        if ((truncatedStr + sentence).length <= maxLength) {
            truncatedStr += sentence + ' ';
        } else {
            break;
        }
    }
    return truncatedStr.trim();
}

function descTeaser(desc) {
	// TODO more efficient
	let doc = document.createElement('div');
	doc.innerHTML = desc;
	return trunc(doc.innerText, 120);
}


export function App( { imgSize } ) {
	const [state, setState] = useState([]);
	const [filters, setFilters] = useState({areas: null, min_age: null, from_date: null, to_date: null, show_full: false});
	useEffect(() => {
		fetch_all_events(state, setState);
	}, []);

	// TODO put these in an effect block so they only run once
	let classes = {};
	let areas = new Set();
	let levels = new Set();
	for (let e of state) {
		if (e.name.startsWith("Private Instruction Session")) {
			continue;
		}
		let c = classes[e.name] || {
			id: e.id,
			name: e.name,
			extra: null,
			price: null,
			duration: null,
			description: e.description,
			shortDesc: null,
			img: null,
			times: [],
		};
		if (!c.extra) {
			c.extra = extraFromName(c.name);
			if (c.extra) {
				areas.add(c.extra.area);
				levels.add(c.extra.level);
			}
		}
		if (!c.img) {
			c.img = imgFromDesc(e.description);
		}
		if (!c.shortDesc) {
			c.shortDesc = descTeaser(e.description);
		}
		c.times.push([new Date(e.startDate + ' ' + e.startTime), new Date(e.endDate + ' ' + e.endTime)]);
		if (!classes[e.name]) {
			classes[e.name] = c;
		}

	}
	let items = Object.values(classes).map((c) => {
		return renderItem({
			id: c.id,
			title: (c.extra && c.extra.shortName) || c.name,
			area: (c.extra && c.extra.area) || "Special Event",
			level: (c.extra || {}).level || null,
			features: ['TODO', 'TODO'],
			price: '$TODO',
			discount: '$TODO2',
			img: c.img,
			imgSize: imgSize,
			shortDesc: c.shortDesc,
		});
	  })


	return (<div>
		<div class="ph-filters">
			<select onChange={console.log}>
				<option>All Areas</option>
				{Array.from(areas).map((a) => <option value={a}>{a}</option>)}
			</select>
			<select onChange={console.log}>
				<option>Any Level</option>
				<option>101-110 Beginner</option>
				<option>111-199 Project</option>
				<option>200+ Intermediate</option>
			</select>
			<select onChange={console.log}>
				<option>No Age Restriction</option>
				<option>12-18 years</option>
				<option>18+</option>
			</select>
			<div>
				<input type="date" id="ph-start"/> to <input type="date" id="ph-end"/>
			</div>
			<div>
				<input type="checkbox" id="ph-show-all"/><label for="ph-show-all">Show Full Classes</label>
			</div>
		</div>
		<div class="ph-grid">{items}</div>
	</div>);
}
