// Every API call in the app goes through apiFetch (JSON) or apiUpload (files).
//
// They handle, in one place:
//   - CSRF: mutating requests send X-CSRFToken. The token is tied to the
//     session, so it goes stale when the session changes (e.g. sign-out and
//     back in); on a CSRF failure the request is retried once with a fresh one.
//   - 402 Payment Required: the new entitlement is pushed into the store, so
//     every page switches to read-only at once.
//   - 401 Unauthorized: the session expired, so sign out and go to /login.
//   - 429 Too Many Requests: turned into a "try again in N" message.
// Any other failure throws an Error carrying the server's `error` message.

let _csrf = null

async function getCsrf(force = false) {
  if (force) _csrf = null
  if (!_csrf) {
    const r = await fetch('/api/csrf-token', { credentials: 'include' })
    _csrf = (await r.json()).token
  }
  return _csrf
}

/** Parse a JSON body, tolerating a response that has none.
 *  A 502 from the platform, or a proxy timeout, is an HTML page — and
 *  `res.json()` on that throws a SyntaxError that says nothing useful. */
async function parseBody(res) {
  if (res.status === 204) return null
  try {
    return await res.json()
  } catch {
    return null
  }
}

/** Did this fail specifically because of the CSRF token? */
function isCsrfFailure(res, data) {
  return res.status === 419
    || (res.status === 400 && typeof data?.error === 'string' && data.error.includes('CSRF'))
}

const MUTATING = ['POST', 'PUT', 'PATCH', 'DELETE']

// Handlers for the two statuses that mean something about the session rather
// than about the request. Registered by App.jsx rather than imported from the
// store: this module is the bottom of the dependency graph, and importing the
// zustand store here would invert that and risk a cycle through App.jsx.
let _onPaymentRequired = null
let _onUnauthorized = null

export function setApiHandlers({ onPaymentRequired, onUnauthorized } = {}) {
  if (onPaymentRequired) _onPaymentRequired = onPaymentRequired
  if (onUnauthorized) _onUnauthorized = onUnauthorized
}

/** The Error thrown for a 402, after updating the stored entitlement. */
function paymentRequiredError(data) {
  _onPaymentRequired?.(data.entitlement)
  const e = new Error(data?.error || 'That needs an active subscription.')
  e.paymentRequired = true
  e.entitlement = data.entitlement
  return e
}

/** POST one file as multipart/form-data under the field name "file". */
export async function apiUpload(path, file) {
  const send = async (csrf) => {
    const fd = new FormData()
    fd.append('file', file)
    // No Content-Type header on purpose: the browser has to set it so it can
    // include the multipart boundary.
    return fetch(path, {
      method: 'POST',
      headers: { 'X-CSRFToken': csrf },
      body: fd,
      credentials: 'include',
    })
  }

  let res = await send(await getCsrf())
  let data = await parseBody(res)
  if (isCsrfFailure(res, data)) {
    res = await send(await getCsrf(true))
    data = await parseBody(res)
  }
  if (res.status === 402 && data?.payment_required) throw paymentRequiredError(data)
  if (!res.ok) throw new Error(data?.error || 'Upload failed')
  return data
}

/**
 * fetch() wrapper for the JSON API. Returns the parsed body, or throws an
 * Error whose message is safe to show the user.
 *
 *   apiFetch('/api/events')
 *   apiFetch('/api/gyms', { method: 'POST', body: JSON.stringify({ name }) })
 */
export async function apiFetch(path, opts = {}) {
  const method = (opts.method || 'GET').toUpperCase()
  const mutating = MUTATING.includes(method)

  const send = async (csrf) => {
    const headers = { 'Content-Type': 'application/json', ...(opts.headers || {}) }
    if (csrf) headers['X-CSRFToken'] = csrf
    return fetch(path, { ...opts, headers, credentials: 'include' })
  }

  let res = await send(mutating ? await getCsrf() : null)
  let data = await parseBody(res)

  if (mutating && isCsrfFailure(res, data)) {
    res = await send(await getCsrf(true))
    data = await parseBody(res)
    // Still refused with a token we have only just been issued: the session
    // itself is gone, and a refresh is genuinely the answer.
    if (isCsrfFailure(res, data)) {
      _csrf = null
      throw new Error('Session expired — please refresh the page.')
    }
  }

  if (res.status === 204) return null
  if (!res.ok) {
    // Out of subscription (not a bad request).
    if (res.status === 402 && data?.payment_required) throw paymentRequiredError(data)
    // Session expired mid-use. /api/auth/me is excluded: a 401 there just
    // means a visitor who is not signed in.
    if (res.status === 401 && path !== '/api/auth/me') {
      _onUnauthorized?.()
      throw new Error('Your session has expired. Please sign in again.')
    }
    // Rate limited: turn Retry-After into plain words.
    if (res.status === 429) {
      const secs = Number(res.headers.get('Retry-After'))
      const wait = Number.isFinite(secs) && secs > 0
        ? ` Try again in ${secs < 60 ? `${secs} seconds` : `${Math.ceil(secs / 60)} minutes`}.`
        : ''
      throw new Error((data?.error || 'Too many attempts.') + wait)
    }
    throw new Error(data?.error || 'Request failed')
  }
  return data
}
