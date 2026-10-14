import { create } from 'zustand'

export const useAuthStore = create((set) => ({
  user:        null,
  // The entitlement envelope from /api/auth/me — the same shape the server
  // returns with a 402, so a refusal can replace it wholesale and every mounted
  // page flips to read-only without another round trip.
  entitlement: null,
  ready:       false,

  setUser:        (user)        => set({ user }),
  setEntitlement: (entitlement) => set({ entitlement }),
  // Sign-in and the boot check both learn the two together, and setting them in
  // one call avoids a render where the user is known but their entitlement is
  // not — which would briefly show the trial banner to a paying subscriber.
  setSession:     (user, entitlement) => set({ user, entitlement }),
  setReady:       (ready)       => set({ ready }),
  logout:         ()           => set({ user: null, entitlement: null }),
}))
