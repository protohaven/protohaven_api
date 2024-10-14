import { useEffect, useState, useMemo } from '@wordpress/element';

export function get_events(pagination) {
    let q_params = {
	rest_route: "/protohaven-events-plugin-api/v1/events",
        endDateAfter: new Date().toISOString().split('T')[0],
        publishedEvent: true,
        archived: false,
        ...pagination,
    };
    const queryString = new URLSearchParams(q_params).toString();
    return fetch('/?' + queryString).then(rep => rep.json());
}

function fetch_remaining_events(pageSize, cb) {
	return fetch_all_events(cb, 1, 2, pageSize);
}

function fetch_all_events(cb, cur=0, tot=1, pageSize=30) {
	if (cur >= tot) {
		return;
	}
	get_events({currentPage: cur, pageSize}).then((rep) => {
		cb(rep.events);
		return fetch_all_events(cb, cur+1, pageSize, Math.min(rep.pagination.totalPages, 50));
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
		fetch(`/?rest_route=/protohaven-events-plugin-api/v1/event_tickets&neon_id=${event_id}`).then(rep => rep.json()).catch(reject).then((data) => {
			tix.inflight--;
			tix.cplt.push(Date.now());
			if (tix.queue.length && tix.cplt.length === 1) {
				setTimeout(processTix, MS);
			}
			if (data === "Error" || data[0].code == "9997") {
				let backoff = Math.random()*MS;
				console.warn(data, "retrying with " + backoff + " backoff");
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
function get_event_tickets_memo(event_id) {
	return useMemo(get_event_tickets, [event_id])(event_id);
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
function FmtTimes( { times, expanded, onExpand } ) {
	times.sort((a, b) => a[1][0] - b[1][0]);
	let expand = [];
	const EXPAND_THRESH = 2;
	for (let [neon_id, dd] of times) {
		expand.push(<div key={neon_id}><a href={infoLink(neon_id)} target="_blank">{dateStr(dd[0])}</a></div>);
		if (!expanded && expand.length >= EXPAND_THRESH) {
			break;
		}
	}

	return (<>
		{expand}
		{!expanded && times.length > EXPAND_THRESH && <div key="expand">(<a href="#" onClick={(e) => {onExpand(true); e.preventDefault();}}>{times.length-EXPAND_THRESH} more</a>)</div>}
	</>);
}

export function Item( {title, area, desc, levelDesc, age, features, discount, img, times, visible, pricing} ) {
	const [expanded, setExpanded] = useState(false);
	let containerClass = "ph-item";
	if (!visible) {
		containerClass += " hidden";
	}

	let imgElem;
	if (img) {
		imgElem = (<div className="ph-img">
			<h3>{area}</h3>
			<img src={img}/>
		</div>);
		containerClass += " cell";
	} else {
		imgElem = <div className="ph-tag">{area}</div>;
		containerClass += " fullbleed";
	}
	const link = (times.length > 0) ? infoLink(times[0][0]) : null;
	const hours = (times.length > 0) ? `${times[0][1][1].getHours() - times[0][1][0].getHours()} hours` : null;
	return (<div className={containerClass} id={title}>
		<div className="ph-content">
			{imgElem}
			<h3 className="ph-title">{title}</h3>

			<div className="ph-desc">{desc}... (<a href={link} target="_blank">more</a>)</div>
		</div>
		<div className="ph-fold">
			<div className="ph-features">
				<FmtTimes times={times} expanded={expanded} onExpand={setExpanded}/>
				<div>{hours}</div>
				<div>Ages {age}+</div>
				<div>{levelDesc}</div>
			</div>
			<button className="ph-footer" onClick={() => gotoURL(link)} disabled={!pricing.remaining}>
				{pricing.price !== null && <div className="ph-price">${pricing.price}</div>}
				{pricing.discount && <div className="ph-discount">(${pricing.discount} for members)</div>}
				{pricing.remaining !== null && <div className="ph-discount">{pricing.remaining} left</div>}
			</button>
		</div>
	</div>);
}

const LEVELS = [
	[200, "Intermediate"],
	[110, "Beginner Project"],
	[100, "Beginner Skills"],
];
function extraFromName(name) {
	// Regex captures area, level, name, and optional paren suffix e.g.
	// Graphics 111: Printed Mugs (Dye Sublimation Clearance)
	// Graphics 111: Printed Mugs
	const regex = /^(\w+)\s+(\d+):\s+(.+?)(?:\s+\((.+)\))?$/;
	const m = name.match(regex);
	if (!m) {
		return {area: "Special Event", level: null, title: name};
	}

	const level = parseInt(m[2]);
	let levelDesc = "";
	if (level) {
		for (let l of LEVELS) {
			if (level >= l[0]) {
				levelDesc = l[1];
				break;
			}
		}
	}

	return {area: m[1], level, levelDesc, title: m[3]};
}


function trunc(inputStr, maxLength) {
    let truncatedStr = '';
    const sentences = inputStr.split(/(?<=[.!?])\s+/);
    for (const sentence of sentences) {
        if ((truncatedStr + sentence).length <= maxLength) {
            truncatedStr += sentence + ' ';
        } else if (truncatedStr.length == 0) {
	    truncatedStr += sentence.substr(0, maxLength);
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
        let node = strong.parentElement.nextElementSibling; // <p className="neonBody"><strong>Header</strong></p>
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
		desc: doc.innerText.substr(0,140),//trunc(doc.innerText, 120),
		features: getFeatures(doc),
	};
}


function process(partial, classes, areas, levels) {
	for (let e of partial) {
		if (e.name.startsWith("Private Instruction Session")) {
			continue;
		}
		let c = classes[e.name] || {
			name: e.name,
			title: null,
			area: null,
			level: null,
			levelDesc: null,
			duration: null,
			description: e.description,
			features: null,
			desc: null,
			img: null,
			age: 16,
			times: {},
		};
		if (!c.title || !c.area || !c.level) {
			let x = extraFromName(c.name);
			if (x) {
				c.title = c.title || x.title;
				c.area = c.area || x.area;
				c.level = c.level || x.level;
				c.levelDesc = c.levelDesc || x.levelDesc;
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
			if (c.features['Age Requirement']) {
				let m = c.features['Age Requirement'].match(/\d+/);
				m = m[0] && parseInt(m[0]) || null;
				c.age = (m !== null) ? Math.min(m, c.age) : c.age;
			}
		}

		c.times[e.id] = [new Date(e.startDate + ' ' + e.startTime), new Date(e.endDate + ' ' + e.endTime)];
		if (!classes[e.name]) {
			classes[e.name] = c;
		}

	}
	return [classes, areas, levels];
}

export function App( { imgSize, initialData } ) {
	const [classes, setClasses] = useState([]);
	const [areas, setAreas] = useState(new Set());
	const [levels, setLevels] = useState(new Set());
	const [filters, setFilters] = useState({area: null, level: null, age: 9999, from_date: null, to_date: null, show_full: true});
	const [pricing, setPricing] = useState({});
	useEffect(() => {
		// Maintain a copy of loading vars so that
		// callbacks have shared context
		let tmpPricing = {};
		let tmpClasses = {};
		let tmpAreas = new Set();
		let tmpLevels = new Set();
		function processPartial(partial) {
			const [c2, a2, l2] = process(partial, tmpClasses, tmpAreas, tmpLevels);
			setClasses(Object.values(tmpClasses));
			setAreas(tmpAreas);
			setLevels(tmpLevels);
			Object.values(c2).forEach((c) => {
				let earliest = Object.keys(c.times).reduce((earliest, key) => {
				    return earliest === null || c.times[key][0] < c.times[earliest][0] ? key : earliest;
				}, null);
				console.log("Earliest", earliest, c.times);
				get_event_tickets(earliest).then((data) => {
					console.log("Got tickets:", earliest);
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
					tmpPricing[c.name] = {price, discount, remaining};
					setPricing({...tmpPricing});
				});
			});
		}
		processPartial(initialData.events, tmpClasses, tmpAreas, tmpLevels);
		if (initialData.pagination.totalResults > initialData.pagination.pageSize) {
			console.log("Initial data" , initialData, "not all classes; fetching remainder");
			fetch_remaining_events(initialData.pagination.pageSize, processPartial);
		}

	}, []);
	const items = classes.map((c) => {
		const p = pricing[c.name] || {remaining: null, price: null, discount: null};
		let timesWithinRange = Object.entries(c.times).filter((t) => (!filters.from_date || t[1][1] >= filters.from_date) && (!filters.to_date || t[1][2] <= filters.to_date));
		const visible = (
			(!filters.area || filters.area === c.area) &&
			c.age <= filters.age &&
			(p === null || p.remaining > 0 || filters.show_full) &&
			(!filters.level || filters.level === c.levelDesc) &&
			((!filters.from_date && !filters.to_date) || timesWithinRange.length > 0)
		)
		return [visible, <Item key={c.name} {...c} times={timesWithinRange} pricing={p} filters={filters} visible={visible} />];
	});
	console.log(items.map((i) => i[1]));
	const any_visible = items.map((i) => i[0]).reduce((a,b) => a || b, false);

	return (<div>
		<div className="ph-filters">
			<select onChange={(e) => {
				setFilters({...filters, area: e.target.value});
			}}>
				<option>All Areas</option>
				{Array.from(areas).map((a) => <option value={a} key={a}>{a}</option>)}
			</select>
			<select onChange={(e) => {
				setFilters({...filters, level: e.target.value});
			}}>
				<option value="">Any Level</option>
				{LEVELS.toReversed().map((l) => <option key={l[0]} value={l[1]}>{l[1]}</option>)}
			</select>
			<select onChange={(e) => {
				setFilters({...filters, age: parseInt(e.target.value)});
			}}>
				<option value="9999">Any Age</option>
				<option value="12">12+</option>
				<option value="16">16+</option>
			</select>
			<select onChange={(e) => {
				setFilters({...filters, show_full: e.target.value === "true"});
			}}>
				<option value={true}>Any Availability</option>
				<option value={false}>Show Available Only</option>
			</select>
			<div>
				<input type="date" id="ph-start" onChange={(e) => {
					setFilters({...filters, from_date: new Date(e.target.value)});
				}}/>
				&nbsp;to&nbsp;
				<input type="date" id="ph-end" onChange={(e) => {
					let d = new Date(e.target.value);
					d.setHours(23, 59, 59, 999); // Inclusive
					setFilters({...filters, to_date: d});
				}}/>
			</div>
		</div>
		<div className="ph-grid">
		{items.map((i) => i[1])}
		{!any_visible && <div className="status-message">
				<div>No classes are available for your search.</div>
				<div>Please broaden your search,
		request <a href="https://form.asana.com/?k=YXgO7epJe3brNGLS6sOw7A&d=1199692158232291" target="_blank">Private Instruction</a>, or <a href="mailto:education@protohaven.org">Contact Us</a>.
				</div>
		</div>}
		</div>
	</div>);
}
