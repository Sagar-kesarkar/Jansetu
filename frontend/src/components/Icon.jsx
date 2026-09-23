/**
 * Inline SVG icons.
 *
 * Hand-drawn rather than pulled from a package: the whole set below is under 2 kB
 * and an icon library is 40× that for the eight glyphs this app uses. They also
 * inherit `currentColor`, so a sector badge recolours by CSS rather than by
 * shipping a second copy of the file.
 *
 * All on a 24-unit grid with a 1.7 stroke, which is what keeps them looking like
 * one family next to the interface type rather than eight separate downloads.
 */
const BASE = {
  width: '1em',
  height: '1em',
  viewBox: '0 0 24 24',
  fill: 'none',
  stroke: 'currentColor',
  strokeWidth: 1.7,
  strokeLinecap: 'round',
  strokeLinejoin: 'round',
  'aria-hidden': 'true',
  focusable: 'false',
}

const PATHS = {
  check: <path d="M20 6 9 17l-5-5" />,
  'check-circle': (
    <>
      <circle cx="12" cy="12" r="9.2" />
      <path d="M8 12.3l2.7 2.7L16 9.8" />
    </>
  ),
  copy: (
    <>
      <rect x="9" y="9" width="11" height="11" rx="2" />
      <path d="M5 15H4.6A1.6 1.6 0 0 1 3 13.4V4.6A1.6 1.6 0 0 1 4.6 3h8.8A1.6 1.6 0 0 1 15 4.6V5" />
    </>
  ),
  info: (
    <>
      <circle cx="12" cy="12" r="9.2" />
      <path d="M12 11v5.5" />
      <path d="M12 7.6h.01" strokeWidth="2.2" />
    </>
  ),
  // --- sectors. Ten codes, ten glyphs; see models/taxonomy.py.
  water: <path d="M12 2.8s6 6.4 6 10.6a6 6 0 0 1-12 0C6 9.2 12 2.8 12 2.8Z" />,
  sanitation: (
    <>
      <path d="M4 8h16" />
      <path d="M6 8v9a3 3 0 0 0 3 3h6a3 3 0 0 0 3-3V8" />
      <path d="M9.5 8V5a2 2 0 0 1 2-2h1a2 2 0 0 1 2 2v3" />
    </>
  ),
  road: (
    <>
      <path d="M6 21 9 3" />
      <path d="M18 21 15 3" />
      <path d="M12 5v3M12 11v3M12 17v3" />
    </>
  ),
  bolt: <path d="M13.5 2.5 5 13.5h5.5L9.8 21.5 18.5 10H13l.5-7.5Z" />,
  health: (
    <>
      <path d="M12 5.5v13M5.5 12h13" />
      <rect x="3" y="3" width="18" height="18" rx="4.5" />
    </>
  ),
  education: (
    <>
      <path d="M2.5 8.5 12 4l9.5 4.5L12 13 2.5 8.5Z" />
      <path d="M6.5 10.7V16c0 1.3 2.5 2.6 5.5 2.6s5.5-1.3 5.5-2.6v-5.3" />
      <path d="M21 9.4V14" />
    </>
  ),
  digital: (
    <>
      <circle cx="12" cy="12" r="9.2" />
      <path d="M2.8 12h18.4" />
      <path d="M12 2.8c2.4 2.5 3.7 5.7 3.7 9.2s-1.3 6.7-3.7 9.2c-2.4-2.5-3.7-5.7-3.7-9.2S9.6 5.3 12 2.8Z" />
    </>
  ),
  housing: (
    <>
      <path d="M3.5 10.5 12 3.5l8.5 7" />
      <path d="M5.5 9.8V20h13V9.8" />
      <path d="M10 20v-5.5h4V20" />
    </>
  ),
  irrigation: (
    <>
      <path d="M3 17.5c2 0 2-1.6 4-1.6s2 1.6 4 1.6 2-1.6 4-1.6 2 1.6 4 1.6" />
      <path d="M3 21c2 0 2-1.6 4-1.6s2 1.6 4 1.6 2-1.6 4-1.6 2 1.6 4 1.6" />
      <path d="M12 12.5V3M12 6.5 8.5 4.5M12 9.5l3.5-2" />
    </>
  ),
  transport: (
    <>
      <rect x="4" y="3.5" width="16" height="13" rx="2.5" />
      <path d="M4 11.5h16" />
      <path d="M7.5 20v-3.5M16.5 20v-3.5" />
      <path d="M8 14.2h.01M16 14.2h.01" strokeWidth="2.2" />
    </>
  ),
  // --- detail-grid glyphs
  clock: (
    <>
      <circle cx="12" cy="12" r="9.2" />
      <path d="M12 7.2V12l3.4 2" />
    </>
  ),
  pin: (
    <>
      <path d="M12 21.5s7-5.9 7-11a7 7 0 1 0-14 0c0 5.1 7 11 7 11Z" />
      <circle cx="12" cy="10.3" r="2.6" />
    </>
  ),
  globe: (
    <>
      <circle cx="12" cy="12" r="9.2" />
      <path d="M2.8 12h18.4" />
      <path d="M12 2.8c2.4 2.5 3.7 5.7 3.7 9.2s-1.3 6.7-3.7 9.2c-2.4-2.5-3.7-5.7-3.7-9.2S9.6 5.3 12 2.8Z" />
    </>
  ),
  doc: (
    <>
      <path d="M14 3.2H7a2 2 0 0 0-2 2v13.6a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V8.2L14 3.2Z" />
      <path d="M13.6 3.4v5h5.2" />
      <path d="M8.6 13h6.8M8.6 16.4h4.6" />
    </>
  ),
  // --- demo simulator. A handset's worth of controls; see DemoSimulator.jsx.
  phone: (
    <path d="M6.6 3.5h2.1a1 1 0 0 1 1 .8l.8 3.4a1 1 0 0 1-.5 1.1l-1.6.9a11.5 11.5 0 0 0 5.9 5.9l.9-1.6a1 1 0 0 1 1.1-.5l3.4.8a1 1 0 0 1 .8 1v2.1a2.1 2.1 0 0 1-2.3 2.1A16.5 16.5 0 0 1 4.5 5.8 2.1 2.1 0 0 1 6.6 3.5Z" />
  ),
  /* The received handset, rotated. Drawn as its own glyph rather than a CSS
     transform on `phone` so it stays legible at 18px, where a 135° rotation
     puts the stroke joins on a diagonal and they blur together. */
  'phone-off': (
    <>
      <path d="M3.2 14.4l2.6-2.6a1 1 0 0 1 1.2-.2l2.3 1.2a1 1 0 0 0 1.2-.2l2.6-2.6a1 1 0 0 0 .2-1.2L12.1 6.5a1 1 0 0 1 .2-1.2l2.6-2.6" />
      <path d="M14.9 2.7a12 12 0 0 1 6.4 6.4" />
      <path d="M3 21 21 3" strokeWidth="2" />
    </>
  ),
  close: <path d="M6 6l12 12M18 6 6 18" />,
  mic: (
    <>
      <rect x="9" y="2.6" width="6" height="11.4" rx="3" />
      <path d="M5.5 11.5a6.5 6.5 0 0 0 13 0" />
      <path d="M12 18v3.2" />
    </>
  ),
  send: <path d="M3.4 11.9 20.5 3.5l-8.4 17.1-1.8-7-6.9-1.7Z" />,
  clip: (
    <path d="M8.5 12.2 14 6.7a3.1 3.1 0 0 1 4.4 4.4l-7.2 7.2a5 5 0 0 1-7.1-7.1l7.4-7.4" />
  ),
  image: (
    <>
      <rect x="3" y="4.5" width="18" height="15" rx="2.5" />
      <circle cx="8.6" cy="10" r="1.6" />
      <path d="M3.6 17.2l4.6-4.3a1.8 1.8 0 0 1 2.5 0l3.4 3.2" />
      <path d="M13.4 14.6l2.2-2a1.8 1.8 0 0 1 2.4 0l2.4 2.1" />
    </>
  ),
}

/** Sector code → glyph. Kept beside the paths so a new sector is one line. */
const SECTOR_ICON = {
  WATER_SUPPLY: 'water',
  SANITATION: 'sanitation',
  ROADS: 'road',
  ELECTRICITY: 'bolt',
  HEALTH: 'health',
  EDUCATION: 'education',
  DIGITAL: 'digital',
  HOUSING: 'housing',
  IRRIGATION: 'irrigation',
  TRANSPORT: 'transport',
}

/** An unmapped sector gets the document glyph rather than a blank square. */
export const sectorIcon = (code) => SECTOR_ICON[code] ?? 'doc'

export default function Icon({ name, size, ...rest }) {
  const glyph = PATHS[name]
  if (!glyph) return null
  return (
    <svg {...BASE} {...(size ? { width: size, height: size } : null)} {...rest}>
      {glyph}
    </svg>
  )
}
