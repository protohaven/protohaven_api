console.log( 'Hello World! (from create-block-protohaven-class-ticker block)' );
fetch("https://api.protohaven.org/event_ticker").then((rep) => {
	if (rep.status != 200) {
		throw Error(rep.status_text);
	}
	return rep.json();
}).then((data) => {
	console.log(data);
	const elem = document.getElementById("protohaven-class-ticker");
	for (let evt of data) {
		let a = document.createElement('a');
		a.href = evt['url'];
		a.target = "_blank";
		let s = `${evt['name']} on ${evt['date']}`;
		if (evt['seats_left'] <= 2) {
			s += ` (${evt['seats_left']} left!)`;
		}
		a.innerHTML = s
		elem.appendChild(a);
	}
});
