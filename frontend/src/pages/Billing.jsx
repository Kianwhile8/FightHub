import { useEffect, useRef, useState } from 'react'
import { Link, useSearchParams, useNavigate } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { toast } from 'sonner'
import { apiFetch } from '../api/client'
import { useAuthStore } from '../store/auth'
import { PLANS, planForRole } from '../constants/pricing'

const DATE = { day: 'numeric', month: 'long', year: 'numeric' }

function fmtDate(iso) {
  if (!iso) return null
  const d = new Date(iso)
  return Number.isNaN(d.getTime()) ? null : d.toLocaleDateString('en-GB', DATE)
}

export default function Billing() {
  const user = useAuthStore(s => s.user)
  const setEntitlement = useAuthStore(s => s.setEntitlement)
  const [params] = useSearchParams()
  const navigate = useNavigate()
  const [busy, setBusy] = useState(false)

  const { data, refetch } = useQuery({
    queryKey: ['billing-status'],
    queryFn: () => apiFetch('/api/billing/status'),
  })

  const ent = data?.entitlement
  const trialDays = data?.trial_days ?? 7
  const billingEnabled = data?.billing_enabled !== false

  // Keep the store in step with this page, so the sidebar banner updates the
  // moment a payment lands rather than on the next full page load.
  useEffect(() => {
    if (ent) setEntitlement(ent)
  }, [ent, setEntitlement])

  // ── return from Stripe ──────────────────────────────────────────────────
  // The webhook that activates the subscription frequently has not arrived by
  // the time the browser gets back here, so a single read would show the user
  // "expired" seconds after they paid. Poll a few times before giving up, and
  // say something reassuring rather than something wrong.
  const handled = useRef(false)
  useEffect(() => {
    if (handled.current) return
    const outcome = params.get('checkout')
    if (!outcome) return
    handled.current = true

    if (outcome === 'cancelled') {
      toast('No payment was taken.')
      navigate('/billing', { replace: true })
      return
    }
    if (outcome !== 'success') return

    let cancelled = false
    ;(async () => {
      for (let attempt = 0; attempt < 3; attempt++) {
        const res = await refetch()
        if (cancelled) return
        if (res.data?.entitlement?.active) {
          setEntitlement(res.data.entitlement)
          toast.success('Thank you — your subscription is active.')
          navigate('/billing', { replace: true })
          return
        }
        await new Promise(r => setTimeout(r, 2000))
      }
      if (cancelled) return
      toast.success('Payment received — your account will update within a minute.')
      navigate('/billing', { replace: true })
    })()

    return () => { cancelled = true }
  }, [params, refetch, navigate, setEntitlement])

  async function go(path, failure) {
    setBusy(true)
    try {
      const d = await apiFetch(path, { method: 'POST' })
      if (!d?.url) throw new Error(failure)
      // A full navigation, not a form POST: the CSP sets form-action 'self', so
      // posting a form at Stripe would be blocked by the browser.
      window.location.assign(d.url)
      // Deliberately left busy — the navigation takes a moment, and a second
      // click in that window opens a second Checkout session.
    } catch (e) {
      toast.error(e.message)
      setBusy(false)
    }
  }

  if (user?.role === 'admin') {
    return (
      <>
        <h1>Subscription</h1>
        <div className="card">
          <p className="sub-status-text">
            Administrator accounts do not require a subscription. You have full
            access to every feature.
          </p>
        </div>
      </>
    )
  }

  const myPlan = planForRole(user?.role) || PLANS.pro
  const otherPlan = myPlan.id === 'pro' ? PLANS.fighter : PLANS.pro

  return (
    <>
      <h1>Subscription</h1>

      {!billingEnabled && (
        <div className="card">
          <p className="sub-status-text">
            Subscriptions are not enabled on this deployment, so every feature is
            currently available at no charge.
          </p>
        </div>
      )}

      {billingEnabled && (
        <>
          <div className="card">
            <StatusBlock ent={ent} trialDays={trialDays} />
            <div className="btn-row" style={{ marginBottom: 0, marginTop: '1.25rem' }}>
              {ent?.state !== 'active' && (
                <button className="btn btn-primary" disabled={busy}
                  onClick={() => go('/api/billing/checkout',
                    'Could not start checkout. Please try again.')}>
                  {busy ? 'Opening checkout…'
                        : ent?.state === 'trialing' ? 'Subscribe now' : 'Subscribe'}
                </button>
              )}
              {ent?.manageable && (
                <button className="btn" disabled={busy}
                  onClick={() => go('/api/billing/portal',
                    'Could not open the billing portal. Please try again.')}>
                  Manage subscription
                </button>
              )}
            </div>
          </div>

          <h2>Plans</h2>
          <div className="plan-grid">
            <PlanCard plan={myPlan} current busy={busy}
              onSubscribe={() => go('/api/billing/checkout',
                'Could not start checkout. Please try again.')}
              state={ent?.state} />
            <PlanCard plan={otherPlan} />
          </div>

          <p className="sub-status-text" style={{ fontSize: 13 }}>
            Billed annually in GBP. Payment is taken by Stripe — FightHub never
            sees your card details. You can cancel at any time and keep access to
            the end of the period you have paid for. See the{' '}
            <Link to="/terms" style={{ textDecoration: 'underline' }}>Terms of Service</Link>
            {' '}for the cancellation and refund terms.
          </p>
        </>
      )}
    </>
  )
}

function StatusBlock({ ent, trialDays }) {
  if (!ent) return <p className="sub-status-text">Checking your subscription…</p>

  const pill = {
    active:   ['sub-pill--active',   'Active'],
    trialing: ['sub-pill--trialing', 'Free trial'],
    comped:   ['sub-pill--comped',   'Complimentary'],
    past_due: ['sub-pill--past-due', 'Payment failed'],
    expired:  ['sub-pill--expired',  'Ended'],
    none:     ['sub-pill--none',     'No subscription'],
    admin:    ['sub-pill--admin',    'Administrator'],
  }[ent.state] || ['sub-pill--none', ent.state]

  const renews = fmtDate(ent.current_period_end)

  let detail
  if (ent.state === 'trialing') {
    const n = ent.trial_days_left ?? 0
    detail = <>Your free trial has <strong>{n === 1 ? '1 day' : `${n} days`}</strong> left. Subscribe at any point and the subscription starts when the trial ends.</>
  } else if (ent.state === 'active' && ent.cancel_at_period_end) {
    detail = <>Your subscription is cancelled and will not renew. You keep full access until <strong>{renews}</strong>.</>
  } else if (ent.state === 'active') {
    detail = <>Your subscription is active{renews ? <> and renews on <strong>{renews}</strong></> : null}.</>
  } else if (ent.state === 'past_due') {
    detail = <>We could not take your renewal payment. Your access continues while Stripe retries — update your card to avoid losing it.</>
  } else if (ent.state === 'comped') {
    detail = <>You have complimentary access to FightHub{ent.comped_until ? <> until <strong>{fmtDate(ent.comped_until)}</strong></> : ', with no end date'}. Nothing to pay.</>
  } else {
    detail = <>FightHub is read-only on your account. You can still browse the fighter database, the rankings and your own record — adding, editing and matchmaking need a subscription. Your {trialDays}-day trial has been used.</>
  }

  return (
    <>
      <div className="sub-status">
        <span className={`sub-pill ${pill[0]}`}>{pill[1]}</span>
      </div>
      <p className="sub-status-text">{detail}</p>
    </>
  )
}

function PlanCard({ plan, current, busy, onSubscribe, state }) {
  return (
    <div className={`card plan-card ${current ? 'plan-card--current' : 'plan-card--other'}`}>
      {current && <div className="plan-tag">Your plan</div>}
      <div className="plan-card-name">{plan.name}</div>
      <div className="plan-priceline">
        <span className="plan-price">{plan.price}</span>
        <span className="plan-period">{plan.period}</span>
      </div>
      <p className="plan-for">{plan.for}</p>
      <ul className="plan-features">
        {plan.features.map(f => <li key={f}>{f}</li>)}
      </ul>
      {current
        ? (state !== 'active' && (
            <button className="btn btn-primary plan-cta" disabled={busy} onClick={onSubscribe}>
              {busy ? 'Opening checkout…' : `Subscribe — ${plan.price}/year`}
            </button>
          ))
        : (
          <p className="plan-period" style={{ textAlign: 'center' }}>
            That is the {plan.name.toLowerCase()} plan
          </p>
        )}
    </div>
  )
}
