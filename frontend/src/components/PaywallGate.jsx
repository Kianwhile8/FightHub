import { Link } from 'react-router-dom'
import { useEntitlement } from '../hooks/useEntitlement'

/**
 * Wraps a write affordance so an unsubscribed account sees an upsell instead.
 *
 * One component rather than a condition edited into every page: there are
 * roughly two dozen write affordances across ten pages, and a per-page `if`
 * means two dozen chances to forget one. The server gates the routes regardless
 * — this only decides what the UI offers.
 *
 *   mode="lock"  (default) replaces the control with a locked button
 *   mode="hide"            renders nothing, for secondary controls where a
 *                          lock would just be noise
 *   mode="panel"           replaces a whole panel with an upsell card
 */
export default function PaywallGate({ children, mode = 'lock', label, title, body }) {
  const { canWrite } = useEntitlement()
  if (canWrite) return children

  if (mode === 'hide') return null

  if (mode === 'panel') {
    return (
      <div className="card paywall-card">
        <div className="paywall-lock" aria-hidden="true">🔒</div>
        <h3 className="paywall-title">{title || 'Subscription required'}</h3>
        <p className="paywall-body">
          {body || 'Your free trial has ended. Reading the database, the rankings and your own record stays free — this feature needs an active subscription.'}
        </p>
        <Link className="btn btn-primary" to="/billing">See plans</Link>
      </div>
    )
  }

  return (
    <Link className="btn paywall-btn" to="/billing">
      <span aria-hidden="true">🔒</span>
      {label || 'Subscribe to unlock'}
    </Link>
  )
}
