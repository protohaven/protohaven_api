// The default @wordpress/scripts Jest environment is jsdom, which does not
// always expose the Node TextEncoder/TextDecoder globals used by ReactDOMServer.
const { TextDecoder, TextEncoder } = require('node:util');

global.TextDecoder = TextDecoder;
global.TextEncoder = TextEncoder;
