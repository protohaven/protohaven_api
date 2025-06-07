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
		fetch(`/?rest_route=/protohaven-events-plugin-api/v1/event_tickets&evt_id=${event_id}`).then(rep => rep.json()).catch(reject).then((data) => {
			tix.inflight--;
			console.log(`Ticket data for ${event_id}:`, data);
			tix.cplt.push((data.cached) ? null : Date.now());
			if (tix.queue.length && tix.cplt.length === 1) {
				setTimeout(processTix, MS/10);
			}
			if (data.data === "Error" || data.data[0].code == "9997") {
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

export const LEVELS = [
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
