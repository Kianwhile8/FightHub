import { lazy, Suspense, useEffect } from 'react'
import { createBrowserRouter, RouterProvider } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { Toaster } from 'sonner'
import Layout from './components/Layout'
import ProtectedRoute from './components/ProtectedRoute'
import RootRoute from './components/RootRoute'
import Spinner from './components/Spinner'
import CookieBanner from './components/CookieBanner'
import { useAuthStore } from './store/auth'
import { apiFetch, setApiHandlers } from './api/client'

const Landing      = lazy(() => import('./pages/Landing'))
const Login        = lazy(() => import('./pages/Login'))
const Dashboard    = lazy(() => import('./pages/Dashboard'))
const FightersList = lazy(() => import('./pages/fighters/FightersList'))
const FighterDetail = lazy(() => import('./pages/fighters/FighterDetail'))
const Matchmake    = lazy(() => import('./pages/fighters/Matchmake'))
const Rankings     = lazy(() => import('./pages/Rankings'))
const History      = lazy(() => import('./pages/History'))
const EventsList   = lazy(() => import('./pages/events/EventsList'))
const EventDetail  = lazy(() => import('./pages/events/EventDetail'))
const GymsList     = lazy(() => import('./pages/gyms/GymsList'))
const GymDetail    = lazy(() => import('./pages/gyms/GymDetail'))
const Profile      = lazy(() => import('./pages/Profile'))
const Billing      = lazy(() => import('./pages/Billing'))
const Admin        = lazy(() => import('./pages/Admin'))
// Named exports off one module, so the three legal pages share a chunk and a
// layout instead of being three copies of the same nineteen lines.
const Terms        = lazy(() => import('./pages/LegalPage').then(m => ({ default: m.TermsPage })))
const Privacy      = lazy(() => import('./pages/LegalPage').then(m => ({ default: m.PrivacyPage })))
const Cookies      = lazy(() => import('./pages/LegalPage').then(m => ({ default: m.CookiesPage })))
const NotFound     = lazy(() => import('./pages/NotFound'))

const queryClient = new QueryClient({
  defaultOptions: { queries: { staleTime: 30_000, retry: 1 } },
})

const Wrap = ({ children }) => <Suspense fallback={<Spinner full />}>{children}</Suspense>

const router = createBrowserRouter([
  // The public landing page. RootRoute redirects anyone already signed in to
  // their dashboard, which is what the `index: true` child of the protected
  // route used to do — so a returning user still never sees this page, and the
  // lazy Landing chunk is never fetched for them.
  { path: '/',      element: <RootRoute><Wrap><Landing /></Wrap></RootRoute> },
  { path: '/login', element: <Wrap><Login /></Wrap> },
  // Outside ProtectedRoute on purpose: someone deciding whether to sign up has
  // to be able to read these, and they have no account yet. The cookie policy
  // in particular is linked from the banner, which shows before sign-in.
  { path: '/terms',   element: <Wrap><Terms /></Wrap> },
  { path: '/privacy', element: <Wrap><Privacy /></Wrap> },
  { path: '/cookies', element: <Wrap><Cookies /></Wrap> },
  {
    // Pathless layout route. It was `path: '/'`, but '/' is now the public
    // landing page above. With no path of its own the children's paths still
    // resolve against '/' exactly as before.
    element: <ProtectedRoute><Layout /></ProtectedRoute>,
    children: [
      { path: ':sport/dashboard',                  element: <Wrap><Dashboard /></Wrap> },
      { path: ':sport/fighters',                   element: <Wrap><FightersList /></Wrap> },
      { path: ':sport/fighters/:id',               element: <Wrap><FighterDetail /></Wrap> },
      { path: ':sport/fighters/:id/matchmake',     element: <Wrap><Matchmake /></Wrap> },
      { path: ':sport/rankings',                   element: <Wrap><Rankings /></Wrap> },
      { path: ':sport/history',                    element: <Wrap><History /></Wrap> },
      { path: 'events',                            element: <Wrap><EventsList /></Wrap> },
      { path: 'events/:id',                        element: <Wrap><EventDetail /></Wrap> },
      { path: 'gyms',                              element: <Wrap><GymsList /></Wrap> },
      { path: 'gyms/:id',                          element: <Wrap><GymDetail /></Wrap> },
      { path: 'profile',                           element: <Wrap><Profile /></Wrap> },
      { path: 'billing',                           element: <Wrap><Billing /></Wrap> },
      { path: 'admin',                             element: <Wrap><Admin /></Wrap> },
    ],
  },
  { path: '*', element: <Wrap><NotFound /></Wrap> },
])

// Registered once, at module scope, so the handlers are in place before the
// first request can be made — an /api/auth/me that raced a useEffect would
// otherwise find them null.
setApiHandlers({
  onPaymentRequired: (entitlement) => {
    useAuthStore.getState().setEntitlement(entitlement)
  },
  onUnauthorized: () => {
    useAuthStore.getState().logout()
    queryClient.clear()
    router.navigate('/login')
  },
})

function AuthInitializer() {
  const { setSession, setReady } = useAuthStore()
  useEffect(() => {
    apiFetch('/api/auth/me')
      .then(d => setSession(d.user, d.entitlement))
      .catch(() => setSession(null, null))
      .finally(() => setReady(true))
  }, [])
  return null
}

export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <AuthInitializer />
      <RouterProvider router={router} />
      {/* Above the router so it shows on every route, signed in or not. */}
      <CookieBanner />
      <Toaster theme="dark" richColors position="bottom-right" />
    </QueryClientProvider>
  )
}
