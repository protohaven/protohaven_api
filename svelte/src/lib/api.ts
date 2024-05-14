
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

export function post(url, data) {
  return fetch(base_url() + url, {
    method: 'POST',
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
