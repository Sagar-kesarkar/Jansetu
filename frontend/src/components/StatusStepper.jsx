/**
 * StatusStepper — wraps and delegates to RequestProgressTimeline.
 */
import RequestProgressTimeline from './RequestProgressTimeline.jsx'

export default function StatusStepper(props) {
  return <RequestProgressTimeline {...props} />
}

export { RequestProgressTimeline }
