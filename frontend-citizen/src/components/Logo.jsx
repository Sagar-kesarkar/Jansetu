/**
 * The JanSetu mark.
 *
 * Prefers `public/logo.png` — the real artwork, an arched bridge carrying a row
 * of people, with a leaf at its footing and a faint mesh across the span — and
 * falls back to an inline SVG of the same device if the file is missing, so the
 * masthead never renders a broken image in front of a judge.
 *
 * The fallback is SVG rather than a smaller raster because the mark is drawn at
 * 38px here and 64px as a favicon, and a low-resolution logo on a high-DPI
 * laptop is the most common way a government prototype looks cheap.
 *
 * Deliberately no wordmark inside this component. `App.jsx` already sets
 * "JanSetu / जनसेतु" in the masthead type, and the artwork's own lettering was
 * cropped away when the mark was extracted — printing the name twice at two
 * different weights is the mistake that crop exists to avoid.
 */
import { useState } from 'react'

export default function Logo({ size = 38, className = '' }) {
  const [raster, setRaster] = useState(true)

  if (raster) {
    return (
      <span className={`logo ${className}`.trim()}>
        <img
          src="/logo.png"
          alt=""
          aria-hidden="true"
          width={size}
          height={size}
          className="logo__img"
          onError={() => setRaster(false)}
        />
      </span>
    )
  }

  return (
    <span className={`logo ${className}`.trim()}>
      <svg
        width={size}
        height={size}
        viewBox="0 0 64 64"
        role="img"
        aria-label="JanSetu"
        className="logo__svg"
      >
        {/* the span */}
        <path d="M11 46 Q32 12 53 46" fill="none" stroke="#a4532a" strokeWidth="3.6" strokeLinecap="round" />
        {/* the deck it carries */}
        <path d="M6 46.5 H58" stroke="#a4532a" strokeWidth="3" strokeLinecap="round" />
        {/* side stays */}
        <path d="M11 46 Q19 33 27 27 M53 46 Q45 33 37 27" fill="none" stroke="#a4532a" strokeWidth="1.4" opacity="0.55" />
        {/* the people on the span, which are the point of the bridge */}
        <circle cx="24" cy="15.5" r="2.4" fill="#a4532a" />
        <circle cx="32" cy="13" r="2.7" fill="#a4532a" />
        <circle cx="40" cy="15.5" r="2.4" fill="#a4532a" />
        <path
          d="M20.5 22 Q24 18.5 27.5 22 M28 20 Q32 16 36 20 M36.5 22 Q40 18.5 43.5 22"
          fill="none"
          stroke="#a4532a"
          strokeWidth="2.4"
          strokeLinecap="round"
        />
        {/* what it is for */}
        <path d="M32 43 Q27.5 41.5 27.5 37 Q32 37.5 32 43 Z" fill="#1f7a3d" />
        <path d="M32 43 Q36.5 41.5 36.5 37 Q32 37.5 32 43 Z" fill="#1f7a3d" />
      </svg>
    </span>
  )
}
