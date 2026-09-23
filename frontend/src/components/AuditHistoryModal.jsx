/**
 * AuditHistoryModal — Privacy-safe chronological audit timeline for citizen tracking.
 */
import React, { useEffect, useRef } from 'react'
import { formatFullDateTime } from '../lib/format.js'

export default function AuditHistoryModal({ data, onClose, language = 'en' }) {
  const modalRef = useRef(null)
  const history = data.history || data.status_history || []

  // Close on Escape key
  useEffect(() => {
    const handleKeyDown = (e) => {
      if (e.key === 'Escape') {
        onClose()
      }
    }
    document.addEventListener('keydown', handleKeyDown)
    return () => document.removeEventListener('keydown', handleKeyDown)
  }, [onClose])

  const token = data.track_token || data.token || ''

  return (
    <div
      style={{
        position: 'fixed',
        top: 0,
        left: 0,
        right: 0,
        bottom: 0,
        background: 'rgba(15, 23, 42, 0.65)',
        backdropFilter: 'blur(4px)',
        zIndex: 9999,
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        padding: '1rem',
      }}
      onClick={onClose}
      role="dialog"
      aria-modal="true"
      aria-labelledby="audit-modal-title"
    >
      <div
        ref={modalRef}
        style={{
          background: '#ffffff',
          borderRadius: '16px',
          maxWidth: '580px',
          width: '100%',
          maxHeight: '85vh',
          display: 'flex',
          flexDirection: 'column',
          boxShadow: '0 20px 25px -5px rgba(0, 0, 0, 0.2), 0 8px 10px -6px rgba(0, 0, 0, 0.2)',
          border: '1px solid #e2e8f0',
        }}
        onClick={(e) => e.stopPropagation()}
      >
        {/* Modal Header */}
        <div
          style={{
            padding: '1.25rem 1.5rem',
            borderBottom: '1px solid #e2e8f0',
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
          }}
        >
          <div>
            <h3
              id="audit-modal-title"
              style={{ margin: 0, fontSize: '1.15rem', color: '#0f172a', fontWeight: 700 }}
            >
              Grievance Activity & Audit Timeline
            </h3>
            {token ? (
              <div style={{ fontSize: '0.825rem', color: '#64748b', marginTop: '2px' }}>
                Tracking Token:{' '}
                <code style={{ fontFamily: 'monospace', fontWeight: 700, color: '#2563eb' }}>
                  {token}
                </code>
              </div>
            ) : null}
          </div>
          <button
            type="button"
            onClick={onClose}
            aria-label="Close dialog"
            style={{
              background: '#f1f5f9',
              border: 'none',
              borderRadius: '50%',
              width: '32px',
              height: '32px',
              cursor: 'pointer',
              fontSize: '1.2rem',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              color: '#475569',
            }}
          >
            ×
          </button>
        </div>

        {/* Modal Body / History List */}
        <div style={{ padding: '1.5rem', overflowY: 'auto', flex: 1 }}>
          <div style={{ position: 'relative', paddingLeft: '1.5rem' }}>
            <div
              style={{
                position: 'absolute',
                top: '8px',
                bottom: '8px',
                left: '7px',
                width: '2px',
                background: '#cbd5e1',
              }}
            />

            {history.length === 0 ? (
              <div style={{ color: '#64748b', fontSize: '0.9rem', fontStyle: 'italic' }}>
                No further updates yet.
              </div>
            ) : (
              history.map((item, idx) => (
                <div key={idx} style={{ position: 'relative', marginBottom: '1.5rem' }}>
                  {/* Dot indicator */}
                  <div
                    style={{
                      position: 'absolute',
                      left: '-1.5rem',
                      top: '2px',
                      width: '16px',
                      height: '16px',
                      borderRadius: '50%',
                      background: idx === history.length - 1 ? '#10b981' : '#3b82f6',
                      border: '3px solid #ffffff',
                      boxShadow: '0 0 0 2px #e2e8f0',
                    }}
                  />
                  {/* Card box */}
                  <div
                    style={{
                      background: '#f8fafc',
                      border: '1px solid #e2e8f0',
                      borderRadius: '10px',
                      padding: '0.85rem 1rem',
                    }}
                  >
                    <div
                      style={{
                        display: 'flex',
                        justifyContent: 'space-between',
                        alignItems: 'flex-start',
                        flexWrap: 'wrap',
                        gap: '4px',
                        marginBottom: '4px',
                      }}
                    >
                      <strong style={{ fontSize: '0.95rem', color: '#1e293b' }}>
                        {item.status_label || item.status_after || 'Status Updated'}
                      </strong>
                      <span
                        style={{
                          fontSize: '0.8rem',
                          color: '#64748b',
                          fontFamily: 'monospace',
                        }}
                      >
                        {formatFullDateTime(item.timestamp || item.changed_at)}
                      </span>
                    </div>
                    {item.desk || item.department ? (
                      <div
                        style={{
                          fontSize: '0.825rem',
                          color: '#2563eb',
                          fontWeight: 600,
                          marginBottom: '4px',
                        }}
                      >
                        🏛️ {item.desk || item.department}
                      </div>
                    ) : null}
                    {item.body_en || item.public_note || item.public_label ? (
                      <p
                        style={{
                          margin: '4px 0 0 0',
                          fontSize: '0.875rem',
                          color: '#334155',
                          lineHeight: 1.45,
                        }}
                      >
                        {item.body_en || item.public_note || item.public_label}
                      </p>
                    ) : null}
                    {item.body_native ? (
                      <p
                        style={{
                          margin: '4px 0 0 0',
                          fontSize: '0.875rem',
                          color: '#475569',
                          fontStyle: 'italic',
                        }}
                      >
                        "{item.body_native}"
                      </p>
                    ) : null}
                  </div>
                </div>
              ))
            )}

            {history.length === 1 ? (
              <div
                style={{
                  color: '#64748b',
                  fontSize: '0.85rem',
                  fontStyle: 'italic',
                  marginTop: '0.5rem',
                  paddingLeft: '4px',
                }}
              >
                No further updates yet.
              </div>
            ) : null}
          </div>
        </div>

        {/* Modal Footer */}
        <div
          style={{
            padding: '0.85rem 1.5rem',
            borderTop: '1px solid #e2e8f0',
            display: 'flex',
            justifyContent: 'flex-end',
            background: '#f8fafc',
            borderRadius: '0 0 16px 16px',
          }}
        >
          <button
            type="button"
            onClick={onClose}
            style={{
              padding: '0.5rem 1.25rem',
              background: '#0f172a',
              color: '#ffffff',
              border: 'none',
              borderRadius: '8px',
              fontSize: '0.875rem',
              fontWeight: 600,
              cursor: 'pointer',
            }}
          >
            Close Audit Log
          </button>
        </div>
      </div>
    </div>
  )
}
