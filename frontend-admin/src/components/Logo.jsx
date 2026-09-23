/**
 * The JanSetu mark.
 *
 * Prefers `public/logo.png` and falls back to an inline SVG of the same device —
 * an arched bridge with people on the span and a leaf at its footing — so the page
 * is never waiting on an asset and never shows a broken image. Drop the artwork at
 * `frontend-admin/public/logo.png` and it takes over on the next reload with no
 * code change; delete it and the SVG comes back.
 *
 * The fallback is SVG rather than a second raster because this mark is drawn at
 * 26px in the form panel and 40px on the dark panel, and a small raster logo on a
 * high-DPI laptop is the most common way a government prototype looks cheap.
 */
import { useState } from 'react'

export function Logo({ size = 36, showWord = false, className = '' }) {
  const [raster, setRaster] = useState(true)

  return (
    <div className={`logo ${className}`.trim()}>
      {raster ? (
        <img
          src="/logo.png"
          alt="JanSetu"
          width={size}
          height={size}
          className="logo__img"
          style={{
            width: `${size}px`,
            height: `${size}px`,
            objectFit: 'contain',
            display: 'block',
            borderRadius: '4px',
          }}
          onError={() => setRaster(false)}
        />
      ) : (
        <svg
          width={size}
          height={size}
          viewBox="0 0 64 64"
          role="img"
          aria-label="JanSetu"
          className="logo__svg"
          style={{ width: `${size}px`, height: `${size}px`, display: 'block' }}
        >
          {/* the span */}
          <path
            d="M9 47 Q32 9 55 47"
            fill="none"
            stroke="currentColor"
            strokeWidth="3.4"
            strokeLinecap="round"
          />
          {/* the deck it carries */}
          <path d="M5 47.5 H59" stroke="currentColor" strokeWidth="3" strokeLinecap="round" />
          {/* hangers */}
          <path
            d="M18 32 V47 M32 15 V47 M46 32 V47"
            stroke="currentColor"
            strokeWidth="1.2"
            opacity="0.5"
          />
          {/* three people on the span — the point of the bridge */}
          <circle cx="25" cy="13" r="2.6" fill="currentColor" />
          <circle cx="32" cy="10.5" r="2.9" fill="currentColor" />
          <circle cx="39" cy="13" r="2.6" fill="currentColor" />
          <path
            d="M21 20 Q25 16.5 28.5 20 M28 18 Q32 14 36 18 M35.5 20 Q39 16.5 43 20"
            fill="none"
            stroke="currentColor"
            strokeWidth="2.4"
            strokeLinecap="round"
          />
          {/* what it is for */}
          <path
            d="M32 44 Q27.5 42.5 27.5 38 Q32 38.5 32 44 Z"
            fill="#2f7d43"
          />
          <path
            d="M32 44 Q36.5 42.5 36.5 38 Q32 38.5 32 44 Z"
            fill="#2f7d43"
          />
        </svg>
      )}

      {showWord ? (
        <span className="logo__word">
          <span className="logo__word-en">JanSetu</span>
          <span className="logo__word-hi">जनसेतु</span>
        </span>
      ) : null}
    </div>
  )
}
