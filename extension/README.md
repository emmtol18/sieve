# Neural Sieve Chrome Extension

## Installation

1. Generate PNG icons from `icon.svg`:
   ```bash
   # Using ImageMagick or any SVG-to-PNG converter
   # Or use an online tool like https://svgtopng.com
   ```

2. Open Chrome and go to `chrome://extensions/`

3. Enable "Developer mode" (top right)

4. Click "Load unpacked" and select this `extension/` folder

## Usage

1. Start the Neural Sieve server: `sieve manage`

2. Select text on any webpage and click the extension icon

3. Or right-click selected text and choose "Save to Neural Sieve"

## Status Indicator

- **Green dot**: Server is running
- **Red dot**: Server is offline (run `sieve manage`)
