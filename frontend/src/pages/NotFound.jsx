import { useNavigate } from 'react-router-dom'

export default function NotFound() {
  const navigate = useNavigate()
  return (
    <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center',
                  height: '100vh', gap: '1rem', background: 'var(--bg)' }}>
      <div style={{ fontSize: 64, fontWeight: 700, color: 'var(--border)' }}>404</div>
      <div style={{ fontSize: 16, color: 'var(--muted)' }}>Page not found.</div>
      <button className="btn btn-primary btn-sm" onClick={() => navigate('/mma/dashboard')}>
        Go to Dashboard
      </button>
    </div>
  )
}
