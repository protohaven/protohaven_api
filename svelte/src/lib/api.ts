
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

export function localtime(d) {
	return new Date(d).toLocaleTimeString("en-US", {timeStyle: 'short'});
}

export function as_datetimelocal(d) {
	d = new Date(d);
	d.setMinutes(d.getMinutes() - d.getTimezoneOffset());
	return d.toISOString().slice(0,16);
}
