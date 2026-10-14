import { useState } from 'react'
import { Link, NavLink, Outlet, useNavigate, useParams } from 'react-router-dom'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { toast } from 'sonner'
import { useAuthStore } from '../store/auth'
import { apiFetch } from '../api/client'
import { lastSport } from '../constants/sports'
import { useEntitlement } from '../hooks/useEntitlement'

// The signed-in app shell: sidebar navigation, the trial/subscription banner,
// and the current page (<Outlet />).

// Inline SVG icon — renders identically on every OS/browser
function Icon({ d, size = 16 }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none"
      stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"
      aria-hidden="true">
      {[].concat(d).map((path, i) => <path key={i} d={path} />)}
    </svg>
  )
}

const ICONS = {
  dashboard: 'M3 12l2-2m0 0l7-7 7 7M5 10v10a1 1 0 001 1h3m10-11l2 2m-2-2v10a1 1 0 01-1 1h-3m-6 0a1 1 0 001-1v-4a1 1 0 011-1h2a1 1 0 011 1v4a1 1 0 001 1m-6 0h6',
  fighters:  ['M17 20h5v-2a3 3 0 00-5.356-1.857M17 20H7m10 0v-2c0-.656-.126-1.283-.356-1.857M7 20H2v-2a3 3 0 015.356-1.857M7 20v-2c0-.656.126-1.283.356-1.857m0 0a5.002 5.002 0 019.288 0M15 7a3 3 0 11-6 0 3 3 0 016 0z'],
  rankings:  'M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z',
  history:   'M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z',
  gyms:      ['M19 21V5a2 2 0 00-2-2H7a2 2 0 00-2 2v16m14 0h2m-2 0h-5m-9 0H3m2 0h5M9 7h1m-1 4h1m4-4h1m-1 4h1m-5 10v-5a1 1 0 011-1h2a1 1 0 011 1v5m-4 0h4'],
  events:    'M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z',
  profile:   ['M16 7a4 4 0 11-8 0 4 4 0 018 0z', 'M12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z'],
  admin:     'M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z',
  signout:   'M17 16l4-4m0 0l-4-4m4 4H7m6 4v1a3 3 0 01-3 3H6a3 3 0 01-3-3V7a3 3 0 013-3h4a3 3 0 013 3v1',
  billing:   ['M3 10h18M5 6h14a2 2 0 012 2v8a2 2 0 01-2 2H5a2 2 0 01-2-2V8a2 2 0 012-2z'],
  menu:      ['M4 6h16', 'M4 12h16', 'M4 18h16'],
  close:     ['M6 18L18 6', 'M6 6l12 12'],
}

/** A one-line strip above the page, for subscription states the user has to
 *  act on (trial ending, payment failed, read-only).
 *
 *  Not dismissible: remembering a dismissal would need localStorage, which
 *  would have to be declared in the cookie policy.
 */
function TrialBanner() {
  const { state, trial_days_left: daysLeft, isLockedOut } = useEntitlement()

  if (state === 'trialing') {
    const n = daysLeft ?? 0
    return (
      <div className={`trial-banner${n <= 2 ? ' trial-banner--warn' : ''}`}>
        <span>
          Free trial — <strong>{n === 1 ? '1 day' : `${n} days`} left</strong>.
        </span>
        <Link className="trial-banner-cta" to="/billing">Subscribe</Link>
      </div>
    )
  }

  if (state === 'past_due') {
    return (
      <div className="trial-banner trial-banner--warn">
        <span>We couldn&rsquo;t take your renewal payment.</span>
        <Link className="trial-banner-cta" to="/billing">Update your card</Link>
      </div>
    )
  }

  if (isLockedOut) {
    return (
      <div className="trial-banner trial-banner--danger">
        <span>Your subscription has ended — FightHub is read-only.</span>
        <Link className="trial-banner-cta" to="/billing">See plans</Link>
      </div>
    )
  }

  return null
}

/** A sidebar link. Highlights itself on the current route and closes the
 *  mobile menu when clicked. */
function NavItem({ to, icon, label, onNavigate }) {
  return (
    <NavLink to={to}
      className={({ isActive }) => `nav-item${isActive ? ' active' : ''}`}
      onClick={onNavigate}>
      <span className="nav-icon"><Icon d={icon} /></span>
      <span>{label}</span>
    </NavLink>
  )
}

export default function Layout() {
  // On a page with no sport in its URL (Events, Gyms, Profile) fall back to the
  // discipline last used, so the sidebar links don't quietly reset to MMA.
  const { sport: routeSport } = useParams()
  const sport = routeSport ?? lastSport()
  const navigate  = useNavigate()
  const { user, logout } = useAuthStore()
  const qc = useQueryClient()
  const [sidebarOpen, setSidebarOpen] = useState(false)

  const logoutMutation = useMutation({
    mutationFn: () => apiFetch('/api/auth/logout', { method: 'POST' }),
    onSuccess: () => { logout(); qc.clear(); navigate('/login') },
    onError: (e) => toast.error(e.message),
  })

  function close() { setSidebarOpen(false) }

  const role   = user?.role
  const picUrl = user?.profile_picture ? `/uploads/${user.profile_picture}` : null

  return (
    <div className="shell">
      {/* Hamburger — mobile only */}
      <button className="mobile-toggle" onClick={() => setSidebarOpen(v => !v)}
        aria-label={sidebarOpen ? 'Close menu' : 'Open menu'}>
        <Icon d={sidebarOpen ? ICONS.close : ICONS.menu} size={20} />
      </button>

      {/* Dim overlay — mobile only, appears behind open sidebar */}
      {sidebarOpen && (
        <div className="sidebar-overlay" onClick={close} aria-hidden="true" />
      )}

      <aside className={`sidebar${sidebarOpen ? ' sidebar--open' : ''}`}>
        <div className="sidebar-header">
          <div className="sidebar-logo">Fight<span>Hub</span></div>
        </div>

        <nav className="sidebar-nav" aria-label="Main navigation">
          <div className="nav-section">General</div>

          <NavItem to={`/${sport}/dashboard`} icon={ICONS.dashboard} label="Dashboard"    onNavigate={close} />
          <NavItem to={`/${sport}/fighters`}  icon={ICONS.fighters}  label="Fighters"     onNavigate={close} />
          <NavItem to={`/${sport}/rankings`}  icon={ICONS.rankings}  label="Rankings"     onNavigate={close} />
          <NavItem to={`/${sport}/history`}   icon={ICONS.history}   label="Fight History" onNavigate={close} />
          <NavItem to="/events"               icon={ICONS.events}    label="Events"       onNavigate={close} />

          {['coach', 'admin'].includes(role) && (
            <>
              <div className="nav-section">Management</div>
              <NavItem to="/gyms" icon={ICONS.gyms} label="Gyms" onNavigate={close} />
            </>
          )}

          {role === 'admin' && (
            <>
              <div className="nav-section">Admin</div>
              <NavItem to="/admin" icon={ICONS.admin} label="Admin Panel" onNavigate={close} />
            </>
          )}
        </nav>

        <div className="sidebar-footer">
          <div className="user-info">
            {picUrl
              ? <img src={picUrl} alt=""
                  style={{ width: 36, height: 36, borderRadius: '50%', objectFit: 'cover',
                           border: '1px solid var(--border)', flexShrink: 0 }} />
              : <div className="user-avatar">{user?.email?.[0]?.toUpperCase()}</div>
            }
            <div style={{ minWidth: 0 }}>
              <div className="user-email">{user?.email}</div>
              <span className="user-role-badge">{user?.role}</span>
            </div>
          </div>

          <NavItem to="/profile" icon={ICONS.profile} label="My Profile" onNavigate={close} />

          {/* Hidden for admins, who never pay. */}
          {role !== 'admin' && (
            <NavItem to="/billing" icon={ICONS.billing} label="Subscription" onNavigate={close} />
          )}

          <button className="nav-item" style={{ color: 'var(--danger)' }}
            onClick={() => { logoutMutation.mutate(); close() }}>
            <span className="nav-icon"><Icon d={ICONS.signout} /></span>
            <span>Sign out</span>
          </button>

          {/* Legal links on every page, not just the profile. */}
          <div className="sidebar-legal">
            <Link to="/terms" onClick={close}>Terms</Link>
            <Link to="/privacy" onClick={close}>Privacy</Link>
            <Link to="/cookies" onClick={close}>Cookies</Link>
          </div>
        </div>
      </aside>

      <main className="main">
        <div className="page-content">
          <TrialBanner />
          <Outlet />
        </div>
      </main>
    </div>
  )
}
