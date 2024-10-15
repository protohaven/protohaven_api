import { get_event_tickets, process, fetch_remaining_events, LEVELS } from './lib';
import {Item} from './item';
import { useEffect, useState } from '@wordpress/element';

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
				get_event_tickets(earliest).then((data) => {
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
			fetch_remaining_events(initialData.pagination.pageSize, processPartial);
		}

	}, []);
	const items = classes.map((c) => {
		const p = pricing[c.name] || {remaining: null, price: null, discount: null};
		let timesWithinRange = Object.entries(c.times).filter((t) => (!filters.from_date || t[1][0] >= filters.from_date) && (!filters.to_date || t[1][1] <= filters.to_date));
		const visible = (
			(!filters.area || filters.area === c.area) &&
			c.age <= filters.age &&
			(p === null || p.remaining > 0 || filters.show_full) &&
			(!filters.level || filters.level === c.levelDesc) &&
			((!filters.from_date && !filters.to_date) || timesWithinRange.length > 0)
		)
		return [visible, <Item key={c.name} {...c} times={timesWithinRange} pricing={p} filters={filters} visible={visible} />];
	});
	const any_visible = items.map((i) => i[0]).reduce((a,b) => a || b, false);

	return (<div>
		<div className="ph-filters">
			<select onChange={(e) => {
				setFilters({...filters, area: e.target.value});
			}}>
				<option value="">All Areas</option>
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
					// When JS parses a date like 2024-10-24, it creates
					// `Date Wed Oct 23 2024 20:00:00 GMT-0400 (Eastern Daylight Time)`
					// But when it parses 2024/10/24, it creates
					// `Date Thu Oct 24 2024 00:00:00 GMT-0400 (Eastern Daylight Time)`
					// We must convert to "slash" notation so as not to accidentally include
					// random dates the day before the from-date
					const from_date = (e.target.value) ? new Date(e.target.value.replace("-", "/")) : null;
					setFilters({...filters, from_date});
				}}/>
				&nbsp;to&nbsp;
				<input type="date" id="ph-end" onChange={(e) => {
					let to_date = (e.target.value) ? new Date(e.target.value.replace("-", "/")) : null;
					if (to_date) {
						to_date.setHours(23, 59, 59, 999); // Inclusive
					}
					setFilters({...filters, to_date});
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
