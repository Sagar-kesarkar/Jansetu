/**
 * Voice capture with the browser's own MediaRecorder — no SDK, nothing billed.
 *
 * Voice is not a garnish on this project. A citizen who cannot write in any
 * script the form offers can still hold a button and speak, and roughly a quarter
 * of adults in the districts this ranks are in that position. The recorded blob
 * goes to `/intake/voice`, where Gemini transcribes it multimodally — which is
 * also why there is no Cloud Speech-to-Text client anywhere in this repo.
 */
import { useEffect, useRef, useState } from 'react'

/** The backend rejects anything past 10 MB; ~2 minutes of Opus is far under it,
 *  and a recording that long is already a failure of the form, not of the codec. */
const MAX_SECONDS = 120

/**
 * Chrome and Firefox disagree about what they will record. Ask for the ones that
 * exist and let the browser pick, rather than hardcoding a MIME type that makes
 * `start()` throw on Safari.
 */
function pickMimeType() {
  const candidates = ['audio/webm;codecs=opus', 'audio/webm', 'audio/ogg;codecs=opus', 'audio/mp4']
  return candidates.find((t) => window.MediaRecorder?.isTypeSupported?.(t)) || ''
}

export default function VoiceRecorder({ onRecorded, disabled }) {
  const [recording, setRecording] = useState(false)
  const [seconds, setSeconds] = useState(0)
  const [micError, setMicError] = useState(null)
  const [previewUrl, setPreviewUrl] = useState(null)

  const recorderRef = useRef(null)
  const chunksRef = useRef([])
  const streamRef = useRef(null)

  // Releasing the microphone matters: on most laptops the OS keeps an indicator
  // lit while a track is live, and a recording light that stays on after the demo
  // is a bad look on a screen share.
  useEffect(() => {
    return () => {
      streamRef.current?.getTracks().forEach((t) => t.stop())
      if (previewUrl) URL.revokeObjectURL(previewUrl)
    }
  }, [previewUrl])

  useEffect(() => {
    if (!recording) return
    const id = setInterval(() => setSeconds((s) => s + 1), 1000)
    return () => clearInterval(id)
  }, [recording])

  useEffect(() => {
    if (recording && seconds >= MAX_SECONDS) stop()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [seconds, recording])

  async function start() {
    setMicError(null)
    if (!navigator.mediaDevices?.getUserMedia || !window.MediaRecorder) {
      setMicError('This browser cannot record audio. Type the message instead.')
      return
    }
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true })
      streamRef.current = stream
      const mimeType = pickMimeType()
      const recorder = new MediaRecorder(stream, mimeType ? { mimeType } : undefined)
      chunksRef.current = []
      recorder.ondataavailable = (e) => {
        if (e.data.size) chunksRef.current.push(e.data)
      }
      recorder.onstop = () => {
        const blob = new Blob(chunksRef.current, { type: recorder.mimeType || 'audio/webm' })
        streamRef.current?.getTracks().forEach((t) => t.stop())
        streamRef.current = null
        setPreviewUrl((old) => {
          if (old) URL.revokeObjectURL(old)
          return URL.createObjectURL(blob)
        })
        onRecorded(blob)
      }
      recorder.start()
      recorderRef.current = recorder
      setSeconds(0)
      setRecording(true)
    } catch (err) {
      // A denied permission is the common case and is not a bug. Say what to do.
      setMicError(
        err?.name === 'NotAllowedError'
          ? 'Microphone permission was blocked. Allow it in the browser address bar, or type the message instead.'
          : 'Could not open the microphone. Type the message instead.',
      )
    }
  }

  function stop() {
    recorderRef.current?.state === 'recording' && recorderRef.current.stop()
    setRecording(false)
  }

  const mmss = `${String(Math.floor(seconds / 60)).padStart(2, '0')}:${String(seconds % 60).padStart(2, '0')}`

  return (
    <div className="recorder">
      <button
        type="button"
        className={`recorder__btn${recording ? ' recorder__btn--recording' : ''}`}
        onClick={recording ? stop : start}
        disabled={disabled}
        aria-label={recording ? 'Stop recording' : 'Start recording'}
      >
        {recording ? '■' : '🎙'}
      </button>

      {recording ? (
        <div className="recorder__status">
          <div className="recorder__timer">{mmss}</div>
          Listening — tap to stop
        </div>
      ) : (
        <div className="recorder__status">
          {previewUrl ? 'Recorded. Play it back, or record again.' : 'Tap and speak in your language'}
        </div>
      )}

      {previewUrl && !recording ? (
        // eslint-disable-next-line jsx-a11y/media-has-caption
        <audio className="recorder__playback" controls src={previewUrl} />
      ) : null}

      {micError ? (
        <p className="field__hint" style={{ color: 'var(--danger)', marginTop: 10 }}>
          {micError}
        </p>
      ) : null}
    </div>
  )
}
