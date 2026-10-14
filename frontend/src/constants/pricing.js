// The prices as the user sees them.
//
// Deliberately hardcoded rather than fetched. The landing page is static
// marketing copy served to anonymous visitors, and an unauthenticated
// /api/billing/prices endpoint would be attack surface and limiter budget
// spent on two numbers that change once a year at most.
//
// These MUST stay in step with PRICE_FIGHTER_PENCE / PRICE_PRO_PENCE in
// app/config.py and with the actual Stripe prices. `flask --app wsgi
// check-deploy` retrieves both Stripe prices and fails if the amounts,
// interval or currency disagree, so a drift here is caught before it can
// show a visitor the wrong number.
export const TRIAL_DAYS = 7

export const PLANS = {
  pro: {
    id: 'pro',
    name: 'Coach / Promoter',
    pence: 2000,
    price: '£20',
    period: 'per year',
    for: 'Gym owners, coaches and promoters',
    roles: ['coach', 'promoter'],
    features: [
      'Gym roster management',
      'Add, edit and log results for your fighters',
      'Unlimited matchmaking across all four disciplines',
      'Create events and venues',
      'The drag-and-drop fight-card builder',
    ],
  },
  fighter: {
    id: 'fighter',
    name: 'Fighter',
    pence: 1000,
    price: '£10',
    period: 'per year',
    for: 'Individual competitors',
    roles: ['fighter'],
    features: [
      'Your own profile and competitive record',
      'The full fighter database',
      'Elo rankings and bands',
      'Opponent suggestions',
      'Hide your record at any time',
    ],
  },
}

// Which plan an account of a given role would buy. Mirrors
// BillingService.price_for_role() on the server, which is the authority —
// this copy only decides which card to highlight on the billing page.
export function planForRole(role) {
  if (role === 'admin') return null
  return role === 'fighter' ? PLANS.fighter : PLANS.pro
}
