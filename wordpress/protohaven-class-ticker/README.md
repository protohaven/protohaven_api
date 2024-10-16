# Protohaven Class Ticker Plugin

This is a wordpress plugin intended for the [Protohaven Wordpress site](https://protohaven.org).

It's designed to headline pages with a list of upcoming classes, in an attempt to advertise and better fill them.

## Technical Details

This plugin relies on the /event_ticker route (see protohaven_api/handlers/index.php) to fetch upcoming classes. This route is hosted on an IONOS VPS (as of Oct 2024) and targeted by https://api.protohaven.org/class_ticker.

## Development

Recommend reading the [Create a Block Tutorial](https://developer.wordpress.org/block-editor/getting-started/tutorial/) from Wordpress to get an understanding of the layout of this Gutenberg block plugin.

Run the build system so the plugin auto-updates on change:

```
npm install
npm run start
```

Start a test wordpress server with symlinks to all plugins so they're auto-installed:

```
cd ..
docker compose up
```
