// Inspired by https://github.com/rhashimoto/promise-throttle
let tix = {queue: [], cplt: [], inflight: []};
const MS = 1000;
const MAXCALL = 5;
function processTix() {
	const now = Date.now();
	while (tix.cplt.length && (tix.cplt[0] === null || tix.cplt[0] < now - MS)) {
		tix.cplt.shift();
	}
	while (tix.queue.length && tix.cplt.length + tix.inflight < MAXCALL) {
		const {event_id, resolve, reject} = tix.queue.shift();
		tix.inflight++;
		let url = `/?rest_route=/protohaven-events-plugin-api/v1/event_tickets&evt_id=${event_id}`;
    if (typeof window !== 'undefined' && window.location.search.includes('nocache=1')) {
      url += '&nocache=1';
    }
		fetch(url).then(rep => rep.json()).catch(reject).then((data) => {
			tix.inflight--;
			console.log(`Ticket data for ${event_id}:`, data);
			tix.cplt.push((data.cached) ? null : Date.now());
			if (tix.queue.length && tix.cplt.length === 1) {
				setTimeout(processTix, MS/10);
			}
			if (data.data === "Error" || (data.data.length && data.data[0].code == "9997")) {
				let backoff = Math.random()*MS;
				console.warn(data, "retrying with " + backoff + " backoff");
				setTimeout(() => {
					tix.queue.push({event_id, resolve, reject});
					processTix();
				}, backoff);
			} else {
				resolve(data.data);
			}
		});
	}
	if (tix.queue.length && tix.cplt.length) {
		setTimeout(processTix, tix.cplt[0] + MS - now);
	}
}
export function get_event_tickets(event_id) {
	return new Promise((resolve, reject) => {
		tix.queue.push({event_id, resolve, reject});
		processTix();
	});
}

async function fetchEventsOnce() {
	let url = `/?rest_route=/protohaven-events-plugin-api/v1/events`;
	if (typeof window !== 'undefined' && window.location.search.includes('nocache=1')) {
		url += '&nocache=1';
	}
	const rep = await fetch(url);
	if (!rep.ok) {
		throw new Error(`Error fetching events: ${rep.status}`);
	}
	const data = await rep.json();
	if (!data || !Array.isArray(data.events)) {
		throw new Error('Invalid event data returned');
	}
	return data;
}

export async function fetch_events(retries = 3, baseDelay = 1000) {
	let lastErr = new Error('Unable to fetch class info');
	for (let attempt = 0; attempt <= retries; attempt++) {
		if (attempt > 0) {
			await new Promise((resolve) => setTimeout(resolve, baseDelay * Math.pow(2, attempt - 1)));
		}
		try {
			const data = await fetchEventsOnce();
			if (data.events.length > 0) {
				return data;
			}
			console.warn(`Attempt ${attempt + 1} to fetch events returned no class data`);
			lastErr = new Error('No class data returned');
		} catch (e) {
			console.warn(`Attempt ${attempt + 1} to fetch events failed`, e);
			lastErr = e;
		}
	}
	throw lastErr;
}

// Map class level to a humanized string
export const LEVELS = [
	[200, "Intermediate"],
	[110, "Beginner Project"],
	[100, "Beginner Skills"],
];
function extraFromName(name) {
	// Regex captures area, level, name, and optional paren suffix e.g.
	// Graphics 111: Printed Mugs (Dye Sublimation Clearance)
	// -> ["Graphics ", "111", "Printed Mugs ", "Dye Sublimation Clearance"]
	// Graphics 111: Printed Mugs
	// -> ["Graphics ", "111", "Printed Mugs"]
	// Graphics: Printed Mugs
	// -> ["Graphics", null, "Printed Mugs"]
	// Printed Mugs
	// -> No capture - list as special event
	const regex = /^([\w+\s]+?)(\d+)?:\s+(.+?)(?:\s+\((.+)\))?$/;
	const m = name.match(regex);
	if (!m) {
		return {area: "Special Event", level: null, title: name};
	}

	const level = m[2] && parseInt(m[2]);
	let levelDesc = "";
	if (level) {
		for (let l of LEVELS) {
			if (level >= l[0]) {
				levelDesc = l[1];
				break;
			}
		}
	}

	return {area: (m[1] || "").replace("Protohaven", "").trim(), level, levelDesc, title: (m[3] || "").replace("at Protohaven", "").trim()};
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
		desc: doc.innerText.substr(0,140),
		features: getFeatures(doc),
	};
}

export function process(events, classes, areas, levels) {
	for (let e of events) {
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
			humanized_info: null,
			humanized_start: null,
			description: e.description,
			features: null,
			desc: null,
			img: e.image_url || null,
			age: 16,
			times: {},
		};
		if (!c.area && e.area) {
			c.area = e.area;
		}
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
			  if (value !== null && !c[key]) {
					c[key] = value;
			  }
			});
			if (c.features['Age Requirement']) {
				let m = c.features['Age Requirement'].match(/\d+/);
				m = m[0] && parseInt(m[0]) || null;
				c.age = (m !== null) ? Math.min(m, c.age) : c.age;
			}
		}
		if (!c.humanized_info && e.humanized_session_info) {
			c.humanized_info = e.humanized_session_info;
		}
		if (!c.humanized_start && e.humanized_start) {
			c.humanized_start = e.humanized_start;
		}

		c.times[e.id] = {
			d0: new Date(e.start),
			d1: new Date(e.end),
			capacity: e.capacity,
			url: e.url,
			sold: null,
		};
		if (!classes[e.name]) {
			classes[e.name] = c;
		}

	}
	return [classes, areas, levels];
}
