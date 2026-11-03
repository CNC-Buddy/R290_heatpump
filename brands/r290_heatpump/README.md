# R290 NextGen branding

Approved identity: a cyan circulation loop with an N-shaped negative space and
amber heat accents; a white/cyan wordmark for the dark dashboard.

## Source and exports

- `custom_components/r290_heatpump/frontend/branding.js` is the common vector
  source for the panel and exports. The UI uses inline SVG with an accessible
  `R290 NextGen` label and system typography, without external requests.
- This directory contains editable SVG exports and PNG copies.
- `custom_components/r290_heatpump/brand/` contains the actual integration
  assets: icon and logo, light/dark variants, standard and `@2x` sizes.
- Icons are transparent 256 × 256 / 512 × 512 PNGs. Logo height is 256 / 512 px.
  The default logo has dark lettering; `dark_logo` has light lettering. The
  emblem itself is the same on both backgrounds. No background tile is embedded.

Home Assistant 2026.3+ discovers the local `brand/` folder automatically. This
does not publish anything to the central brands repository or external services.
See the [official brand-image documentation](https://contributors.home-assistant.io/core/integrations/brands/).

To regenerate, run `node scripts/build_brand.mjs` from the project directory
with Playwright installed and, if needed, `CHROMIUM_EXECUTABLE` pointing to a
browser. The exporter renders only locally supplied artwork in a headless browser
and blocks network requests. System fonts affect PNG text metrics; the supplied
exports were rendered using Segoe UI on Windows. The script also writes a local
light/dark preview to `artifacts/r290-nextgen-brand.png`. It does not build a release.

The release file list includes PNG/SVG assets and requires all eight brand PNGs.
These assets are included in the local 1.5.0b23 installation package. No Home
Assistant deployment has been performed.

## Installed icon verification

On 2026-11-02, the running HA 2026.10.4 integration tile loaded the local
`/api/brands/integration/r290_heatpump/dark_icon.png` and displayed the approved
icon in a fresh browser tab. The user subsequently confirmed the icon appeared.
The earlier placeholder is consistent with a cached image; no brand-file change
was required. Refresh the integrations page (Ctrl+F5) if that placeholder remains.
