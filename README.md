# playout

This is Frikanalen's third-generation CasparCG-based playout, in early development.

## TODO

* Observability
* Play log generation
* Management API

## Config

You can place this file in .env and it will be loaded:
```
# URL for broadcast graphics website
GRAPHICS_URL=http://fk.dev.local/graphics
# URL for FK API
FK_API=http://fk.dev.local/api/v2
# Media prefix for CasparCG
CASPAR_MEDIA_URL_PREFIX=http://fk.dev.local/ui
# CasparCG IP adress
CASPAR_HOST=127.0.0.1
```

## Development

Config management is currently very inelegant but this will change. See src/config.ts

```bash
# Get dependencies
yarn
# Generate client code from OpenAPI spec
yarn run generate

yarn run dev
```