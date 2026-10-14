import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { toast } from 'sonner'
import { apiFetch } from '../../api/client'
import { useAuthStore } from '../../store/auth'
import Spinner from '../../components/Spinner'
import PaywallGate from '../../components/PaywallGate'
import { useEntitlement } from '../../hooks/useEntitlement'
import { parseLocalDate, startOfToday } from '../../utils/date'

/**
 * Split events into what is still to come and what has already happened.
 *
 * Upcoming runs soonest-first (the next event is the one you want at the top);
 * previous runs most-recent-first. Events with no date sit in Upcoming — a
 * promoter has announced them without fixing a date, so they have not happened
 * yet, and burying them in the past is how they get forgotten.
 */
/** "Phoenix Centre — Andover", falling back to the name when no town is set. */
function venueLabel(v) {
  const where = [v.city, v.address].filter(Boolean)[0]
  return where ? `${v.name} — ${where}` : v.name
}

function splitByDate(events) {
  const today = startOfToday()
  const upcoming = [], previous = []

  for (const ev of events) {
    const d = parseLocalDate(ev.date)
    if (!d) { upcoming.push(ev); continue }
    // An event happening today is still upcoming, not past.
    ;(d < today ? previous : upcoming).push(ev)
  }

  // Undated events sort last within Upcoming rather than first.
  const time = (ev) => (parseLocalDate(ev.date)?.getTime() ?? Infinity)
  upcoming.sort((a, b) => time(a) - time(b))
  previous.sort((a, b) => time(b) - time(a))
  return { upcoming, previous }
}

function eventStatus(dateStr) {
  const d = parseLocalDate(dateStr)
  if (!d) return { label: 'TBD', cls: 'status-upcoming' }
  const today = startOfToday()
  if (d.getTime() === today.getTime()) return { label: 'Today', cls: 'status-today' }
  if (d < today) return { label: 'Past', cls: 'status-past' }
  return { label: 'Upcoming', cls: 'status-upcoming' }
}

export default function EventsList() {
  const navigate = useNavigate()
  const { user } = useAuthStore()
  const { canWrite } = useEntitlement()
  const qc = useQueryClient()
  const [showForm, setShowForm] = useState(false)
  // Upcoming first: the common question is "what's next", not "what happened".
  const [tab, setTab] = useState('upcoming')
  // '' = no venue, 'new' = fill in a new one, otherwise an existing venue id.
  const [venueMode, setVenueMode] = useState('')

  // Role eligibility and current entitlement, kept apart — see GymsList.
  const roleCanCreate = ['promoter', 'admin'].includes(user?.role)
  const canCreate = roleCanCreate && canWrite

  const { data: eventsData, isLoading } = useQuery({
    queryKey: ['events'],
    queryFn: () => apiFetch('/api/events'),
  })

  const { data: venuesData } = useQuery({
    queryKey: ['venues'],
    queryFn: () => apiFetch('/api/venues'),
  })

  const createMutation = useMutation({
    mutationFn: (body) => apiFetch('/api/events', { method: 'POST', body: JSON.stringify(body) }),
    onSuccess: (d) => {
      qc.invalidateQueries({ queryKey: ['events'] })
      toast.success(`${d.event.name} created.`)
      setShowForm(false)
    },
    onError: (e) => toast.error(e.message),
  })

  function handleCreate(e) {
    e.preventDefault()
    const fd = new FormData(e.target)
    const body = {
      name: fd.get('name').trim(),
      max_bouts: +fd.get('max_bouts'),
      date: fd.get('date') || null,
      time: fd.get('time') || null,
      description: fd.get('description').trim() || null,
    }
    if (venueMode === 'new') {
      const vName = (fd.get('venue_name') || '').trim()
      if (!vName) { toast.error('Give the new venue a name, or choose "No venue".'); return }
      // Sent nested so the server creates the venue and the event together —
      // a half-created venue with no event is worse than a failed submit.
      body.venue = {
        name: vName,
        address: (fd.get('venue_address') || '').trim() || null,
        city: (fd.get('venue_city') || '').trim() || null,
        capacity: fd.get('venue_capacity') || null,
      }
    } else if (venueMode) {
      body.venue_id = +venueMode
    }
    createMutation.mutate(body)
    e.target.reset()
    setVenueMode('')
  }

  if (isLoading) return <Spinner />

  const events = eventsData?.events ?? []
  const venues = venuesData?.venues ?? []

  const { upcoming, previous } = splitByDate(events)
  const shown = tab === 'upcoming' ? upcoming : previous

  return (
    <>
      <h1>Events</h1>
      <div className="toolbar">
        <div style={{ flex: 1 }} />
        {roleCanCreate && (
          <PaywallGate label="Subscribe to create events">
            <button className="btn btn-primary btn-sm" onClick={() => setShowForm(v => !v)}>
              {showForm ? 'Cancel' : '+ New Event'}
            </button>
          </PaywallGate>
        )}
      </div>

      {showForm && (
        <div className="card">
          <h2>New Event</h2>
          <form onSubmit={handleCreate}>
            <div className="form-group">
              <label className="form-label">Event name</label>
              <input name="name" required autoFocus />
            </div>
            <div className="form-row-3">
              <div className="form-group">
                <label className="form-label">Date</label>
                <input name="date" type="date" />
              </div>
              <div className="form-group">
                <label className="form-label">Time</label>
                <input name="time" type="time" />
              </div>
              <div className="form-group">
                <label className="form-label">Bouts on the card</label>
                {/* The card can be arranged once it is full, so this is what
                    decides when that phase opens. */}
                <input name="max_bouts" type="number" min="5" max="20"
                  defaultValue="8" required />
                <div style={{ fontSize: 11, marginTop: 3, color: 'var(--muted-2)' }}>
                  Between 5 and 20
                </div>
              </div>
            </div>
            <div className="form-group">
              <label className="form-label">Venue</label>
              <select className="select-input" value={venueMode}
                onChange={e => setVenueMode(e.target.value)}>
                <option value="">No venue / to be confirmed</option>
                {venues.map(v => (
                  <option key={v.id} value={v.id}>{venueLabel(v)}</option>
                ))}
                <option value="new">+ Add a new venue…</option>
              </select>
            </div>

            {venueMode === 'new' && (
              <div className="subform">
                <div className="form-row">
                  <div className="form-group">
                    <label className="form-label">Venue name</label>
                    <input name="venue_name" placeholder="Phoenix Centre" autoFocus />
                  </div>
                  <div className="form-group">
                    <label className="form-label">Town / city</label>
                    <input name="venue_city" placeholder="Andover" />
                  </div>
                </div>
                <div className="form-row">
                  <div className="form-group">
                    <label className="form-label">Address</label>
                    <input name="venue_address" placeholder="Charlton Road" />
                  </div>
                  <div className="form-group">
                    <label className="form-label">Capacity</label>
                    <input name="venue_capacity" type="number" min="1" placeholder="Optional" />
                  </div>
                </div>
                <div style={{ fontSize: 12, color: 'var(--muted-2)' }}>
                  The venue is saved separately, so you can reuse it for your next event.
                </div>
              </div>
            )}
            <div className="form-group">
              <label className="form-label">Description</label>
              <textarea name="description" />
            </div>
            <button type="submit" className="btn btn-primary btn-sm" disabled={createMutation.isPending}>
              {createMutation.isPending ? 'Creating…' : 'Create Event'}
            </button>
          </form>
        </div>
      )}

      <div className="seg-tabs" role="tablist" aria-label="Filter events">
        <button role="tab" aria-selected={tab === 'upcoming'}
          className={`seg-tab${tab === 'upcoming' ? ' active' : ''}`}
          onClick={() => setTab('upcoming')}>
          Upcoming <span className="seg-count">{upcoming.length}</span>
        </button>
        <button role="tab" aria-selected={tab === 'previous'}
          className={`seg-tab${tab === 'previous' ? ' active' : ''}`}
          onClick={() => setTab('previous')}>
          Previous <span className="seg-count">{previous.length}</span>
        </button>
      </div>

      {shown.length === 0
        ? (
          <div className="empty">
            {events.length === 0
              ? 'No events yet.'
              : tab === 'upcoming' ? 'No upcoming events.' : 'No previous events.'}
          </div>
        )
        : shown.map(ev => {
          const { label, cls } = eventStatus(ev.date)
          const evDate = parseLocalDate(ev.date)
          const day   = evDate ? evDate.getDate() : '–'
          const month = evDate ? evDate.toLocaleString('default', { month: 'short' }).toUpperCase() : ''
          return (
            <div key={ev.id} className="event-card" onClick={() => navigate(`/events/${ev.id}`)}
              style={ev.photo ? {
                backgroundImage: `linear-gradient(rgba(0,0,0,.6), rgba(0,0,0,.75)), url(/uploads/${ev.photo})`,
                backgroundSize: 'cover', backgroundPosition: 'center',
                color: '#fff',
              } : {}}>
              <div className="event-card-header">
                <div className="event-date-block" style={ev.photo ? { background: 'rgba(255,255,255,.15)', color: '#fff' } : {}}>
                  <div className="event-day">{day}</div>
                  <div className="event-month">{month}</div>
                </div>
                <div style={{ flex: 1 }}>
                  <div className="event-title" style={ev.photo ? { color: '#fff' } : {}}>{ev.name}</div>
                  <div className="event-meta" style={ev.photo ? { color: 'rgba(255,255,255,.75)' } : {}}>
                    {ev.time && `${ev.time} · `}
                    {ev.venue_name
                      ? <>{ev.venue_name}{ev.venue_location && ` · ${ev.venue_location}`}</>
                      : 'Venue to be confirmed'}
                  </div>
                  <div style={{ marginTop: 8 }}>
                    <span className={`event-status ${cls}`}>{label}</span>
                  </div>
                </div>
              </div>
              {ev.description && (
                <div style={{ marginTop: '.75rem', fontSize: 13, color: ev.photo ? 'rgba(255,255,255,.7)' : 'var(--muted)' }}>
                  {ev.description}
                </div>
              )}
            </div>
          )
        })
      }
    </>
  )
}
