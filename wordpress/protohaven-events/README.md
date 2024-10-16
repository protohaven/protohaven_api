# Protohaven Event Explorer Plugin

This is a wordpress plugin intended for the [Protohaven Wordpress site](https://protohaven.org), specifically the [classes page](https://www.protohaven.org/classes).

It fetches upcoming events directly from Neon, reformats the data normally displayed in the original [event list](https://protohaven.app.neoncrm.com/np/clients/protohaven/eventList.jsp) (hosted and controlled by Neon) and renders it in a filterable grid.

Notably improved from the old Neon page: the number of remaining seats as well as the discount price for members is displayed.

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
