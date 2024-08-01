
function base_ws() {
  if (window.location.href.indexOf("localhost") === -1) {
      return "wss://api.protohaven.org";
  }
  return  "ws://localhost:5000";
}

function base_url() {
  if (window.location.href.indexOf("localhost") === -1) {
      return "https://api.protohaven.org";
  }
  return  "http://localhost:5000";
}

function json_req(url, data, method) {
  return fetch(base_url() + url, {
    method,
    headers: {
      'Accept': 'application/json',
      'Content-Type': 'application/json'
    },
    body: JSON.stringify(data),
  }).then((rep) => rep.text())
    .then((body) => {
      try {
	    return JSON.parse(body);
      } catch (err) {
	    throw Error(`Invalid reply from server: ${body}`);
      }
    });
}

export function post(url, data) {
  return json_req(url, data, 'POST');
}

export function patch(url, data) {
  return json_req(url, data, 'PATCH');
}

export function put(url, data) {
  return json_req(url, data, 'PUT');
}

export function del(url, data) {
  return json_req(url, data, 'DELETE');
}

export function get(url) {
  return fetch(base_url() + url).then((rep)=>rep.text())
    .then((body) => {
      try {
	    return JSON.parse(body);
      } catch (err) {
	    throw Error(`Invalid reply from server: ${body}`);
      }
    });
}

export function open_ws(url) {
	return new WebSocket(base_ws() + url);
}

export function isodate(d) {
	return new Date(d).toJSON().slice(0,10);
}

export function isodatetime(d) {
	// ISO 8601 datetime string without milliseconds
	return new Date(d).toISOString().slice(0,-5)+"Z";
}

export function localtime(d) {
	return new Date(d).toLocaleTimeString("en-US", {timeStyle: 'short'});
}

export function as_datetimelocal(d) {
	d = new Date(d);
	d.setMinutes(d.getMinutes() - d.getTimezoneOffset());
	return d.toISOString().slice(0,16);
}

export function parse_8601_basic(input) {
  	// https://stackoverflow.com/questions/43898263/parse-iso-8601-basic-datetime-format-in-javascript
	// ISO 8601 dates allow removal of punctuation - this is done in RRULE strings as it messes with
	// parsing of the rest of the string.
	  return new Date(Date.UTC(
	    parseInt(input.slice(0, 4), 10),
	    parseInt(input.slice(4, 6), 10) - 1,
	    parseInt(input.slice(6, 8), 10),
	    parseInt(input.slice(9, 11), 10),
	    parseInt(input.slice(11, 13), 10),
	    parseInt(input.slice(13,15), 10)
	  ));
}
