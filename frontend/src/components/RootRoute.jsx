import { Navigate } from 'react-router-dom'
import { useAuthStore } from '../store/auth'
import { lastSport } from '../constants/sports'
import Spinner from './Spinner'

// The mirror image of ProtectedRoute: holds the public landing page at `/`
// and bounces anyone already signed in straight to their dashboard, so a
// returning user never sees the marketing page they have already bought.
//
// Waiting on `ready` matters. Rendering the landing page during the
// /api/auth/me round trip would flash marketing copy at a signed-in user on
// every cold load of the root URL.
export default function RootRoute({ children }) {
  const { user, ready } = useAuthStore()
  if (!ready) return <Spinner full />
  if (user)   return <Navigate to={`/${lastSport()}/dashboard`} replace />
  return children
}
