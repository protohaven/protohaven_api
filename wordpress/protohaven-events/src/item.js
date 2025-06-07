import { useEffect, useState } from '@wordpress/element';

function gotoURL(url){
	window.open(url, '_blank').focus();
}

function ap(hours) {
	return ((hours > 12) ? hours-12 : hours).toString() + ((hours > 11) ? 'pm' : 'am');
}
function dateStr(d1) {
	return `${d1.toLocaleString('default', { weekday: 'short' })}, ${d1.toLocaleString('default', { month: 'short' })} ${d1.getDate()}, ${ap(d1.getHours())}`;
}

function FmtTimes( { times, expanded, onExpand } ) {
	times.sort((a, b) => a[1].d0 - b[1].d0);
	let expand = [];
	const EXPAND_THRESH = 2;
	for (let [evt_id, dd] of times) {
		let left = "";
		if (dd.capacity !== null && dd.sold != null) {
			if (dd.capacity - dd.sold > 0) {
				left = <span className="ph-discount">({dd.capacity - dd.sold} left)</span>;
			} else {
				left = <span className="ph-discount">(sold out)</span>;
			}
		}
		expand.push(<div key={evt_id}>
			<a href={dd.url} target="_blank">{dateStr(dd.d0)}</a>
			&nbsp;{left}
		</div>);
		if (!expanded && expand.length >= EXPAND_THRESH) {
			break;
		}
	}

	return (<>
		{expand}
		{!expanded && times.length > EXPAND_THRESH && <div key="expand">(<a href="#" onClick={(e) => {onExpand(true); e.preventDefault();}}>{times.length-EXPAND_THRESH} more</a>)</div>}
	</>);
}

export function Item( {title, area, desc, levelDesc, age, features, img, times, visible} ) {
	const [expanded, setExpanded] = useState(false);
	let containerClass = "ph-item";
	if (!visible) {
		containerClass += " hidden";
	}
	let imgElem;
	if (img) {
		imgElem = (<div className="ph-img" style={{'backgroundImage': `url(${img})`}}>
			<h3>{area}</h3>
		</div>);
		containerClass += " cell";
	} else {
		imgElem = <div className="ph-tag">{area}</div>;
		containerClass += " fullbleed";
	}
	const link = (times.length > 0) ? times[0][1].url : null;
	const hours = (times.length > 0) ? `${times[0][1].d1.getHours() - times[0][1].d0.getHours()} hours` : null;
	const price = ((times.length > 0) ? times[0][1].price : null) || null;
	const discount = ((times.length > 0) ? times[0][1].discount : null) || null;
	const total_remaining = times.map((t) => (t[1].capacity - t[1].sold) || 0).reduce((acc, curr) => acc+curr, 0);

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
			<button className="ph-footer" onClick={() => gotoURL(link)} disabled={!total_remaining}>
				{price !== null && <div className="ph-price">${price}</div>}
				{discount && <div className="ph-discount">(${discount} for members)</div>}
			</button>
		</div>
	</div>);
}
