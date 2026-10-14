// App root: React Query, the router, and the boot-time session check.
//
// Routes are split into public pages (landing, login, legal) and a protected
// group rendered inside <Layout> (sidebar + page). Every page is lazy-loaded.

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

// Shows a spinner while a lazy page's code is downloading.
const Wrap = ({ children }) => <Suspense fallback={<Spinner full />}>{children}</Suspense>

const router = createBrowserRouter([
  // Public landing page. RootRoute sends anyone already signed in straight to
  // their dashboard.
  { path: '/',      element: <RootRoute><Wrap><Landing /></Wrap></RootRoute> },
  { path: '/login', element: <Wrap><Login /></Wrap> },
  // Legal pages are public: people must be able to read them before signing up.
  { path: '/terms',   element: <Wrap><Terms /></Wrap> },
  { path: '/privacy', element: <Wrap><Privacy /></Wrap> },
  { path: '/cookies', element: <Wrap><Cookies /></Wrap> },
  {
    // Signed-in area. A pathless layout route: children resolve against '/'.
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

// How the API client reacts to session-level failures (see api/client.js).
// Registered at module scope so they exist before the first request is made.
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

// On first load, ask the server who is signed in. Routes wait for `ready`.
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
