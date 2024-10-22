import { useEffect, useState } from '@wordpress/element';

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
		imgElem = (<div className="ph-img" style={{'backgroundImage': `url(${img})`}}>
			<h3>{area}</h3>
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
