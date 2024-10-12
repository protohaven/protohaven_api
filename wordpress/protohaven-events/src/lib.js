
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

function fetch_all_events(cb, cur=0, tot=1) {
	if (cur >= tot) {
		return;
	}
	get_events({currentPage: cur, pageSize: 50}).then((rep) => {
		cb(rep.events);
		// TODO uncomment
		// return fetch_all_events(cb, cur+1, Math.min(rep.pagination.totalPages, 20));
	});
}

export function get_event_tickets(event_id) {
	return fetch(`http://localhost:8080/?rest_route=/protohaven-events-plugin-api/v1/event_tickets?neon_id=${event_id}`).then(rep => rep.json());
}

function gotoEvent(event_id){
	window.open('https://protohaven.app.neoncrm.com/np/clients/protohaven/event.jsp?event=' + event_id, '_blank').focus();
}


function ap(hours) {
	return ((hours > 12) ? hours-12 : hours).toString() + ((hours > 11) ? 'pm' : 'am');
}
function dateStr(d1) {
	return `${d1.toLocaleString('default', { month: 'short' })} ${d1.getDate()}, ${ap(d1.getHours())}`;
}
function fmtTimes(times, expanded, onExpand) {
	times.sort((a, b) => a[0] - b[0]);
	const [d1, d2] = times[0];
	let hrs = <div>{d2.getHours() - d1.getHours()} hours</div>;
	if (times.length > 1 && !expanded) {
		return [<div>{dateStr(d1)}</div>,<div>(<a href="#" onClick={onExpand}>{times.length-1} more</a>)</div>, hrs];
	} else if (times.length > 1 && expanded) {
		return [...times.map((t) => <div>{dateStr(t[0])}</div>), hrs];
	}
	return [<div>{dateStr(d1)}</div>, hrs];
}

function fmtAges(features) {
	if (features['Age Requirement']) {
		let age = features['Age Requirement'].match(/\d+/);
		if (age) {
			return <div>Ages {age[0]}+</div>;
		}
	}
	return <div>Ages 16+</div>;
}

export function renderItem({id, title, area, desc, level, features, price, discount, img, times, imgSize}, expanded, onExpand) {
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
	let featList = [...fmtTimes(times, expanded, onExpand), fmtAges(features)];
	return (<div class={containerClass} id={id}>
		<div class="ph-content">
			{img}
			<	h3>{title}</h3>

			<div class="ph-desc">{desc} (<a href="#">more</a>)</div>
		</div>
		<div class="ph-fold">
			<div class="ph-features">{featList}</div>
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

function getFeatures(doc) {
    const features = {};
    const sections = doc.querySelectorAll('strong');
    sections.forEach(strong => {
        const sectionTitle = strong.textContent.trim();
        const sectionContent = [];
        let node = strong.parentElement.nextElementSibling; // <p class="neonBody"><strong>Header</strong></p>
	if (node) {
        	features[sectionTitle] = node.innerText;
	}
    });
    return features;
}

function parseDesc(desc) {
	let doc = document.createElement('div');
	doc.innerHTML = desc;
	let imgElem = doc.getElementsByTagName('img');
	return {
		img: (imgElem.length !== 0) ? imgElem[0].src : null,
		desc: trunc(doc.innerText, 120),
		features: getFeatures(doc),
	};
}


function process(partial) {
	let classes = {};
	let areas = new Set();
	let levels = new Set();
	for (let e of partial) {
		if (e.name.startsWith("Private Instruction Session")) {
			continue;
		}
		let c = classes[e.name] || {
			id: e.id,
			name: e.name,
			title: null,
			area: null,
			level: null,
			price: null,
			discount: null,
			duration: null,
			description: e.description,
			features: null,
			desc: null,
			img: null,
			times: [],
		};
		if (!c.title || !c.area || !c.level) {
			let extra = extraFromName(c.name);
			if (extra) {
				c.title = c.title || extra.title;
				c.area = c.area || extra.area;
				c.level = c.level || extra.level;
				areas.add(extra.area);
				levels.add(extra.level);
			}
		}
		if (!c.img || !c.desc || !c.features) {
			Object.entries(parseDesc(e.description)).forEach(([key, value]) => {
			    if (value !== null) {
				c[key] = value;
			    }
			});
		}
		c.times.push([new Date(e.startDate + ' ' + e.startTime), new Date(e.endDate + ' ' + e.endTime)]);
		if (!classes[e.name]) {
			classes[e.name] = c;
		}

	}
	return [Object.values(classes), areas, levels];
}

export function App( { imgSize } ) {
	const [classes, setClasses] = useState([]);
	const [areas, setAreas] = useState(new Set());
	const [levels, setLevels] = useState(new Set());
	const [filters, setFilters] = useState({areas: null, min_age: null, from_date: null, to_date: null, show_full: false});
	const [expansions, setExpansions] = useState({});
	console.log("Classes now", classes);
	useEffect(() => {
		fetch_all_events((partial) => {
			const [c2, a2, l2] = process(partial);
			setClasses([...classes, ...c2]);
			let newExp = {...expansions};
			for (let c of c2) {
				newExp[c.name] = false;
			}
			setExpansions(newExp);
			setAreas(areas.add(...a2));
			setLevels(levels.add(...l2));
		});
	}, []);


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
				<option>12-16 years</option>
				<option>16+</option>
			</select>
			<div>
				<input type="date" id="ph-start"/> to <input type="date" id="ph-end"/>
			</div>
			<div>
				<input type="checkbox" id="ph-show-all"/><label for="ph-show-all">Show Full Classes</label>
			</div>
		</div>
		<div class="ph-grid">{classes.map((e) => {
			let expanded = expansions[e.name];
			return renderItem(e, expanded, () => {
				let newExp = {...expansions};
				newExp[e.name] = !expanded;
				setExpansions(newExp);
			})
		})}</div>
	</div>);
}
