// The CSRF token is tied to the session cookie, so it stops being valid
// whenever the session is replaced — most obviously on sign-out, which clears
// the session server-side and invalidates the token this module is holding.
// Every mutating request therefore retries once with a fresh token before it
// gives up, otherwise signing out and straight back in would fail on a stale
// token and the only way through would be a manual page refresh.
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
  // Event and gym photos are gated the same as any other write, so uploads get
  // the same 402 treatment as apiFetch.
  if (res.status === 402 && data?.payment_required) {
    _onPaymentRequired?.(data.entitlement)
    const e = new Error(data?.error || 'That needs an active subscription.')
    e.paymentRequired = true
    e.entitlement = data.entitlement
    throw e
  }
  if (!res.ok) throw new Error(data?.error || 'Upload failed')
  return data
}

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
    // 402 means the account is out of subscription, not that the request was
    // wrong. The server sends the current entitlement back with the refusal, so
    // pushing it into the store here flips every mounted page to read-only
    // immediately rather than on the next /api/auth/me.
    if (res.status === 402 && data?.payment_required) {
      _onPaymentRequired?.(data.entitlement)
      const e = new Error(data?.error || 'That needs an active subscription.')
      e.paymentRequired = true
      e.entitlement = data.entitlement
      throw e
    }
    // The 8-hour session expired mid-use. Until now this surfaced as a bare
    // "Login required." toast on whatever page the user was on, with nothing
    // bouncing them anywhere — so every subsequent query failed the same way.
    // /api/auth/me is excluded because a 401 there is the normal answer for a
    // visitor who is simply not signed in.
    if (res.status === 401 && path !== '/api/auth/me') {
      _onUnauthorized?.()
      throw new Error('Your session has expired. Please sign in again.')
    }
    // 429 carries Retry-After; turning it into plain words saves every call
    // site from having to.
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
