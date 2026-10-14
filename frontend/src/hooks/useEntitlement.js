import { useAuthStore } from '../store/auth'

/**
 * What this account may do, for deciding whether to render a write affordance.
 *
 * Fails OPEN when the entitlement is not yet known. The server is the
 * enforcement point — every gated route returns 402 regardless of what the
 * client believes — so the only job here is to avoid offering a button that is
 * going to fail. A button that 402s is a moment's annoyance; a button hidden
 * from someone who has paid, because a store value had not loaded yet, is a
 * support email.
 */
export function useEntitlement() {
  const user = useAuthStore(s => s.user)
  const entitlement = useAuthStore(s => s.entitlement)

  const canWrite = !entitlement || entitlement.active === true

  return {
    ...(entitlement || {}),
    canWrite,
    isAdmin: user?.role === 'admin',
    // True only when we know the account is locked out, so a banner or an
    // upsell panel never flashes while the answer is still unknown.
    isLockedOut: Boolean(entitlement) && entitlement.active !== true,
  }
}
