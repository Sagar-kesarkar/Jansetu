/**
 * The live demo simulator: a mock handset, floating over the citizen site.
 * Redesigned into 3 distinct interaction states:
 * 1. Compact Teaser Card
 * 2. Explanatory Channel Chooser (.demo.window)
 * 3. Full Channel Simulator (WhatsApp / SMS / IVR) + Close Pill
 */
import { forwardRef, useCallback, useEffect, useRef, useState } from 'react'

import Icon from './Icon.jsx'
import IvrPane from './sim/IvrPane.jsx'
import SmsPane from './sim/SmsPane.jsx'
import WhatsAppPane from './sim/WhatsAppPane.jsx'

export const DEMO_STATES = {
  TEASER: 'teaser',
  CHOOSER: 'chooser',
  SIMULATOR: 'simulator',
}

export const CHANNELS = {
  WHATSAPP: 'whatsapp',
  SMS: 'sms',
  IVR: 'ivr',
}

const TABS = [
  { key: CHANNELS.WHATSAPP, label: 'WhatsApp' },
  { key: CHANNELS.SMS, label: 'SMS' },
  { key: CHANNELS.IVR, label: 'IVR Call' },
]

export default function DemoSimulator() {
  const [demoState, setDemoState] = useState(DEMO_STATES.TEASER)
  const [activeChannel, setActiveChannel] = useState(CHANNELS.WHATSAPP)
  const panelRef = useRef(null)
  const triggerRef = useRef(null)

  // Escape key closes simulator/chooser and returns to TEASER state
  useEffect(() => {
    if (demoState === DEMO_STATES.TEASER) return
    const onKey = (e) => {
      if (e.key === 'Escape') {
        setDemoState(DEMO_STATES.TEASER)
        triggerRef.current?.focus()
      }
    }
    document.addEventListener('keydown', onKey)
    return () => document.removeEventListener('keydown', onKey)
  }, [demoState])

  const openChooser = useCallback(() => {
    setDemoState(DEMO_STATES.CHOOSER)
  }, [])

  const collapseToTeaser = useCallback(() => {
    setDemoState(DEMO_STATES.TEASER)
    triggerRef.current?.focus()
  }, [])

  const launchChannel = useCallback((channel) => {
    setActiveChannel(channel)
    setDemoState(DEMO_STATES.SIMULATOR)
  }, [])

  return (
    <>
      {demoState === DEMO_STATES.TEASER ? (
        <DemoTeaser ref={triggerRef} onOpen={openChooser} />
      ) : null}

      {demoState === DEMO_STATES.CHOOSER ? (
        <DemoChannelChooser
          onCollapse={collapseToTeaser}
          onSelectChannel={launchChannel}
        />
      ) : null}

      {demoState === DEMO_STATES.SIMULATOR ? (
        <div className="sim-container">
          <div
            className="sim"
            ref={panelRef}
            role="dialog"
            aria-label="Live Demo Simulator"
            aria-modal="true"
          >
            <header className="sim__head">
              <div className="sim__head-text">
                <strong className="sim__head-title">Live Demo Simulator</strong>
                <span className="sim__head-sub">Real submissions, simulated handset</span>
              </div>
              <button
                type="button"
                className="sim__close"
                onClick={collapseToTeaser}
                aria-label="Close simulator"
              >
                ×
              </button>
            </header>

            <div className="sim__tabs" role="tablist" aria-label="Channel">
              {TABS.map((t) => (
                <button
                  key={t.key}
                  type="button"
                  role="tab"
                  aria-selected={activeChannel === t.key}
                  className={`sim__tab${activeChannel === t.key ? ' sim__tab--on' : ''}`}
                  onClick={() => setActiveChannel(t.key)}
                >
                  {t.label}
                </button>
              ))}
            </div>

            {/* The phone frame with the selected channel pane */}
            <div className="sim__phone">
              <div className="sim__screen">
                {activeChannel === CHANNELS.WHATSAPP ? <WhatsAppPane key="wa" /> : null}
                {activeChannel === CHANNELS.SMS ? <SmsPane key="sms" /> : null}
                {activeChannel === CHANNELS.IVR ? <IvrPane key="ivr" /> : null}
              </div>
            </div>
          </div>

          <button
            type="button"
            className="demo-close-pill"
            onClick={collapseToTeaser}
            aria-label="Close demo simulator"
          >
            <span style={{ fontSize: '1.1rem', lineHeight: 1 }}>×</span> Close
          </button>
        </div>
      ) : null}
    </>
  )
}

const DemoTeaser = forwardRef(function DemoTeaser({ onOpen }, ref) {
  return (
    <button
      type="button"
      ref={ref}
      className="demo-teaser"
      onClick={onOpen}
      aria-expanded="false"
      aria-label="Open live demo options"
    >
      <div className="demo-teaser__head">
        <span className="demo-teaser__dot" aria-hidden="true" />
        <span className="demo-teaser__title">Demo</span>
        <span className="demo-teaser__expand" aria-hidden="true">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
            <line x1="7" y1="17" x2="17" y2="7"></line>
            <polyline points="7 7 17 7 17 17"></polyline>
          </svg>
        </span>
      </div>
      <p className="demo-teaser__body">
        See how rural communities can report local needs using WhatsApp, SMS, or IVR.
      </p>
      <div className="demo-teaser__link">
        View demo →
      </div>
    </button>
  )
})

function DemoChannelChooser({ onCollapse, onSelectChannel }) {
  const firstBtnRef = useRef(null)

  useEffect(() => {
    firstBtnRef.current?.focus()
  }, [])

  return (
    <div className="demo-chooser" role="region" aria-label="JanSetu channel demo chooser">
      <div className="demo-chooser__head">
        <span className="demo-chooser__dot" aria-hidden="true" />
        <span className="demo-chooser__title">.demo.window</span>
        <button
          type="button"
          className="demo-chooser__collapse"
          onClick={onCollapse}
          aria-label="Collapse demo chooser"
        >
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
            <polyline points="18 15 12 9 6 15"></polyline>
          </svg>
        </button>
      </div>

      <div className="demo-chooser__body">
        <div className="demo-chooser__line">
          <span className="demo-chooser__prompt">&gt;</span> JanSetu channel demos
        </div>
        <div className="demo-chooser__line">
          <span className="demo-chooser__prompt">&gt;</span> For rural communities and people with limited digital access.
        </div>
        <div className="demo-chooser__line">
          <span className="demo-chooser__prompt">&gt;</span> Register local needs without using the website.
        </div>
        <div className="demo-chooser__line" style={{ marginTop: '8px' }}>
          <span className="demo-chooser__prompt">&gt;</span> Choose a channel:
        </div>

        <div className="demo-chooser__actions">
          <button
            type="button"
            ref={firstBtnRef}
            className="demo-chooser__btn"
            onClick={() => onSelectChannel(CHANNELS.WHATSAPP)}
          >
            <span className="demo-chooser__prompt">&gt;</span> [WhatsApp demo]
          </button>
          <button
            type="button"
            className="demo-chooser__btn"
            onClick={() => onSelectChannel(CHANNELS.SMS)}
          >
            <span className="demo-chooser__prompt">&gt;</span> [SMS demo]
          </button>
          <button
            type="button"
            className="demo-chooser__btn"
            onClick={() => onSelectChannel(CHANNELS.IVR)}
          >
            <span className="demo-chooser__prompt">&gt;</span> [IVR demo]
          </button>
        </div>
      </div>
    </div>
  )
}

