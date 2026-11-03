// Shared vector artwork for the panel and the exported Home Assistant brands.
// No external fonts, images or network requests are required by the panel.
const band = 'M52 0C23 0 0 23 0 52V108C0 137 23 160 52 160H81L50 129C39 128 30 119 30 108V52C30 40 40 30 52 30C58 30 63 32 68 37L110 79V37L89 16C79 6 66 0 52 0Z';
const cap = 'M0 108C0 137 23 160 52 160H81L50 129C28 134 8 125 0 108Z';

export function brandMark() {
  return `<g fill="#34d2ec"><path d="${band}"/><path d="${band}" transform="rotate(180 80 80)"/></g><g fill="#ffb268"><path d="${cap}"/><path d="${cap}" transform="rotate(180 80 80)"/></g>`;
}

export function brandIcon() {
  return `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 160 160" role="img" aria-label="R290 NextGen">${brandMark()}</svg>`;
}

export function brandLogo(dark = true) {
  return `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1000 160" role="img" aria-label="R290 NextGen"><g>${brandMark()}</g><g font-family="Segoe UI, Inter, system-ui, sans-serif" font-size="112" letter-spacing="-3"><text x="191" y="119" fill="${dark ? '#edf5fa' : '#163746'}" font-weight="750">R290</text><text x="483" y="119" fill="${dark ? '#34d2ec' : '#087d98'}" font-weight="600">NextGen</text></g></svg>`;
}
