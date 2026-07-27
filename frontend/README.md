# VisionDesk Frontend

The VisionDesk frontend is a React 19 and Vinext browser workspace for the
project's local YOLO detection service.

## Development

```powershell
npm ci
npm run dev:local
```

The browser application runs at `http://127.0.0.1:3000` and connects to
`ws://127.0.0.1:8765/ws/detect` by default.

Override the socket URL before building when necessary:

```powershell
$env:NEXT_PUBLIC_DETECTION_WS_URL="ws://127.0.0.1:9000/ws/detect"
npm run build
```

## Validation

```powershell
npm test
npm run lint
```

`npm test` creates the production Vinext build and checks the rendered
application shell, metadata, social card, starter cleanup, and core source
contracts.
