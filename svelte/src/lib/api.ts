/* eslint-disable @typescript-eslint/no-explicit-any */
export function base_ws() {
	// Use ws:// if http://, or wss:// if https://
	return window.location.origin.replace('http', 'ws');
}

function _trunc(body: string) {
	if (!body) {
		return 'null';
	}
	let msg = body.toString().substr(0, 256);
	if (body.length > 255) {
		msg += '...';
	}
	return msg;
}

function json_req(
	url: string,
	data: unknown,
	method: string,
	signal: AbortSignal | null = null
): Promise<any> {
	return fetch(url, {
		method,
		headers: {
			Accept: 'application/json',
			'Content-Type': 'application/json'
		},
		body: JSON.stringify(data),
		signal: signal
	})
		.then((rep) => {
			return Promise.all([rep.status, rep.statusText, rep.text()]);
		})
		.then(([status, statusText, body]) => {
			if (status !== 200) {
				console.log(status, statusText, body);
				throw Error(`${status} ${statusText}: ${_trunc(body)}`);
			}

			try {
				return JSON.parse(body);
			} catch (err) {
				throw Error(`JSON parse error: ${_trunc(body)}`);
			}
		});
}

export function post(url: string, data: unknown, signal: AbortSignal | null = null): Promise<any> {
	return json_req(url, data, 'POST', signal);
}

export function patch(url: string, data: unknown): Promise<any> {
	return json_req(url, data, 'PATCH');
}

export function put(url: string, data: unknown): Promise<any> {
	return json_req(url, data, 'PUT');
}

export function del(url: string, data: unknown): Promise<any> {
	return json_req(url, data, 'DELETE');
}

export function get(url: string, signal?: AbortSignal | null): Promise<any> {
	return fetch(url, { method: 'get', signal })
		.then((rep) => rep.text())
		.then((body) => {
			try {
				return JSON.parse(body);
			} catch (err) {
				throw Error(`Invalid reply from server: ${body}`);
			}
		});
}

export function open_ws(url: string) {
	return new WebSocket(base_ws() + url);
}

export function isodate(d: string | Date) {
	// Note: this was d.toJSON().slice(0,10)
	// but that approach converts to UTC before
	// formatting, so e.g. 2026-03-26 8pm => 2026-03-27.
	if (typeof d === 'string') {
		// Conversion from string to date - must have timestamp to
		// properly parse into local timezone
		d = d.indexOf('T') === -1 ? new Date(d + 'T12:00:00') : new Date(d);
	}
	const mm = (d.getMonth() + 1).toString().padStart(2, '0');
	const dd = d.getDate().toString().padStart(2, '0');
	return `${d.getFullYear()}-${mm}-${dd}`;
}

export function isodatetime(d: string | Date) {
	// ISO 8601 datetime string without milliseconds
	// This is explicitly in UTC.
	return new Date(d).toISOString().slice(0, -5) + 'Z';
}

export function localtime(d: string | Date) {
	return new Date(d).toLocaleTimeString('en-US', { timeStyle: 'short' });
}

export function as_datetimelocal(d: string | Date) {
	d = new Date(d);
	d.setMinutes(d.getMinutes() - d.getTimezoneOffset());
	return d.toISOString().slice(0, 16);
}

export function parse_8601_basic(input: string) {
	// https://stackoverflow.com/questions/43898263/parse-iso-8601-basic-datetime-format-in-javascript
	// ISO 8601 dates allow removal of punctuation - this is done in RRULE strings as it messes with
	// parsing of the rest of the string.
	return new Date(
		Date.UTC(
			parseInt(input.slice(0, 4), 10),
			parseInt(input.slice(4, 6), 10) - 1,
			parseInt(input.slice(6, 8), 10),
			parseInt(input.slice(9, 11), 10),
			parseInt(input.slice(11, 13), 10),
			parseInt(input.slice(13, 15), 10)
		)
	);
}
