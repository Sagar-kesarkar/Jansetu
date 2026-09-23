/**
 * The 13 languages come from `GET /capabilities`, never from a constant here.
 *
 * The backend's `app/i18n/languages.py` is the source of truth. Hardcoding the
 * list would mean adding the 14th language in two places, and the version that
 * gets forgotten is always the one on screen.
 *
 * Options are labelled in the language's own script first — a Bengali speaker
 * scanning for "বাংলা" should not have to find "Bengali" in English to get there.
 */
export default function LanguagePicker({ languages, value, onChange, disabled }) {
  return (
    <label className="field">
      <span className="field__label">Language / भाषा</span>
      <select
        className="select"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        disabled={disabled || !languages?.length}
      >
        {languages?.length ? (
          languages.map((lang) => (
            <option key={lang.code} value={lang.code}>
              {lang.native} — {lang.name}
            </option>
          ))
        ) : (
          <option value="hi">हिन्दी — Hindi</option>
        )}
      </select>
      <span className="field__hint">
        {languages?.length
          ? `${languages.length} languages supported. Speak or write in yours — the reply comes back in it too.`
          : 'Loading the supported languages…'}
      </span>
    </label>
  )
}
