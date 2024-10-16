# Protohaven Airtable Grid Wordpress Plugin

This is a wordpress plugin primarily intended for the Protohaven [Team](https://www.protohaven.org/team/) page.

It allows us to [share a form](https://airtable.com/appZIwlIgaq1Ps28Y/pagqysKHSMnSunCDO/form ) for folks to submit a picture and bio to, which we can then approve for display in Wordpress by clicking a checkbox in Airtable. This should reduce the effort to edit and maintain attribution to our staff, board, and volunteers.

## Technical Details

This plugin as configured in Wordpress (as of October 2024) pulls from the [Instructor Capabilities table](https://airtable.com/applultHGJxHNg69H/tbltv8tpiCqUnLTp4?blocks=hide) as well as a new [Volunteers & Staff table](https://airtable.com/appZIwlIgaq1Ps28Y/tblgwvc07mvLg3zds/viwPqQYMpOKTLpbgj?blocks=hide). These aren't used directly, but rather the plugins do a server-side fetch from a [Wordpress base](https://airtable.com/appc6WQNsGvcKtTvb?) that syncs in just the data we want to show. The API key is restricted to this base, which prevents things like instructor emails from ever getting leaked out.

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
