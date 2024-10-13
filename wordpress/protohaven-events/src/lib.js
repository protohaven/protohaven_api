
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
	get_events({currentPage: cur, pageSize: 30}).then((rep) => {
		cb(rep.events);
		return fetch_all_events(cb, cur+1, Math.min(rep.pagination.totalPages, 20));
	});
}


// Inspired by https://github.com/rhashimoto/promise-throttle
let tix = {queue: [], cplt: [], inflight: []};
const MS = 1000;
const MAXCALL = 5;
function processTix() {
	const now = Date.now();
	while (tix.cplt.length && tix.cplt[0] < now - MS) {
		tix.cplt.shift();
	}
	while (tix.queue.length && tix.cplt.length + tix.inflight < MAXCALL) {
		const {event_id, resolve, reject} = tix.queue.shift();
		tix.inflight++;
		fetch(`http://localhost:8080/?rest_route=/protohaven-events-plugin-api/v1/event_tickets&neon_id=${event_id}`).then(rep => rep.json()).catch(reject).then((data) => {
			tix.inflight--;
			tix.cplt.push(Date.now());
			if (tix.queue.length && tix.cplt.length === 1) {
				setTimeout(processTix, MS);
			}
			if (data[0].code == "9997") {
				let backoff = Math.random()*MS;
				console.warn("Ratelimited; retrying with " + backoff + " backoff");
				setTimeout(() => {
					tix.queue.push({event_id, resolve, reject});
					processTix();
				}, backoff);
			} else {
				resolve(data);
			}
		});
	}
	if (tix.queue.length && tix.cplt.length) {
		setTimeout(processTix, tix.cplt[0] + MS - now);
	}
}
function get_event_tickets(event_id) {
	return new Promise((resolve, reject) => {
		tix.queue.push({event_id, resolve, reject});
		processTix();
	});
}

function gotoURL(url){
	window.open(url, '_blank').focus();
}


function ap(hours) {
	return ((hours > 12) ? hours-12 : hours).toString() + ((hours > 11) ? 'pm' : 'am');
}
function dateStr(d1) {
	return `${d1.toLocaleString('default', { month: 'short' })} ${d1.getDate()}, ${ap(d1.getHours())}`;
}


function infoLink(eid) {
	return `https://protohaven.app.neoncrm.com/np/clients/protohaven/event.jsp?event=${eid}`;
}
function fmtTimes(times, expanded, onExpand) {
	times.sort((a, b) => a[0] - b[0]);
	const [tid, d1, d2] = times[0];
	let hrs = <div key="hrs">{d2.getHours() - d1.getHours()} hours</div>;
	if (times.length > 1 && !expanded) {
		return [
			<div key={tid}><a href={infoLink(tid)} target="_blank">{dateStr(d1)}</a></div>,
			<div key="expand">(<a href="#" onClick={onExpand}>{times.length-1} more</a>)</div>,
			hrs,
		];
	} else if (times.length > 1 && expanded) {
		return [...times.map((t) => <div key={t[0]}><a href={infoLink(t[0])} target="_blank">{dateStr(t[1])}</a></div>), hrs];
	}
	return [<div key={tid}><a href={infoLink(tid)} target="_blank">{dateStr(d1)}</a></div>, hrs];
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

export function Item(props) {
	const {title, area, desc, level, features, discount, img, times} = props;
	const [expanded, setExpanded] = useState(false);
	const [pricing, setPricing] = useState({price: null, discount: null, remaining: null});
	useEffect(() => {
		get_event_tickets(times[0][0]).then((data) => {
			let price = null;
			let discount = null;
			let remaining = null;
			data.forEach((p) => {
				if (p.name === 'Single Registration') {
					price = p.fee;
					remaining = p.numberRemaining;
				} else if (p.name === 'Member Rate') {
					discount = p.fee;
				}
			});
			setPricing({price, discount, remaining});
		});
	}, []);

	let containerClass = "ph-item";
	let imgElem;
	if (img) {
		imgElem = (<div class="ph-img">
			<h3>{area}</h3>
			<img src={img}/>
		</div>);
		containerClass += " cell";
	} else {
		imgElem = <div class="ph-tag">{area}</div>;
		containerClass += " fullbleed";
	}
	let featList = [...fmtTimes(times, expanded, () => setExpanded(true)), fmtAges(features)];
	return (<div class={containerClass} id={title}>
		<div class="ph-content">
			{imgElem}
			<h3>{title}</h3>

			<div class="ph-desc">{desc} (<a href={times[0][0]} target="_blank">more</a>)</div>
		</div>
		<div class="ph-fold">
			<div class="ph-features">{featList}</div>
			<button class="ph-footer" onClick={() => gotoURL(times[0][0])} disabled={!pricing.remaining}>
				{pricing.price !== null && <div class="ph-price">${pricing.price}</div>}
				{pricing.discount && <div class="ph-discount">(${pricing.discount} for members)</div>}
				{pricing.remaining !== null && <div class="ph-discount">{pricing.remaining} left</div>}
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
		return {area: "Special Event", level: null, title: name};
	}
	return {area: m[1], level: m[2], title: m[3]};
}


function trunc(inputStr, maxLength) {
    let truncatedStr = '';
    const sentences = inputStr.split(/(?<=[.!?])\s+/);
    for (const sentence of sentences) {
        if ((truncatedStr + sentence).length <= maxLength) {
            truncatedStr += sentence + ' ';
        } else if (truncatedStr.length == 0) {
	    truncatedStr += sentence.substr(0, maxLength-3) + '...';
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
			name: e.name,
			title: null,
			area: null,
			level: null,
			duration: null,
			description: e.description,
			features: null,
			desc: null,
			img: null,
			times: [],
		};
		if (!c.title || !c.area || !c.level) {
			let x = extraFromName(c.name);
			if (x) {
				c.title = c.title || x.title;
				c.area = c.area || x.area;
				c.level = c.level || x.level;
				areas.add(x.area);
				levels.add(x.level);
			}
		}
		if (!c.img || !c.desc || !c.features) {
			Object.entries(parseDesc(e.description)).forEach(([key, value]) => {
			    if (value !== null) {
				c[key] = value;
			    }
			});
		}

		c.times.push([e.id, new Date(e.startDate + ' ' + e.startTime), new Date(e.endDate + ' ' + e.endTime)]);
		if (!classes[e.name]) {
			classes[e.name] = c;
		}

	}
	return [Object.values(classes).map((c) => <Item key={c.name} {...c} />),
		areas,
		levels
	];
}

export function App( { imgSize } ) {
	const [classes, setClasses] = useState([]);
	const [areas, setAreas] = useState(new Set());
	const [levels, setLevels] = useState(new Set());
	const [filters, setFilters] = useState({areas: null, min_age: null, from_date: null, to_date: null, show_full: false});
	useEffect(() => {
		fetch_all_events((partial) => {
			const [c2, a2, l2] = process(partial);
			setClasses([...classes, ...c2]);
			setAreas(areas.add(...a2));
			setLevels(levels.add(...l2));
		});
	}, []);


	return (<div>
		<div class="ph-filters">
			<select onChange={console.log}>
				<option>All Areas</option>
				{Array.from(areas).map((a) => <option value={a} key={a}>{a}</option>)}
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
		<div class="ph-grid">{classes}</div>
	</div>);
}
