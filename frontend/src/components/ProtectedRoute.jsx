import { Navigate } from 'react-router-dom'
import { useAuthStore } from '../store/auth'
import Spinner from './Spinner'

export default function ProtectedRoute({ children }) {
  const { user, ready } = useAuthStore()
  if (!ready) return <Spinner full />
  if (!user)  return <Navigate to="/login" replace />
  return children
}
