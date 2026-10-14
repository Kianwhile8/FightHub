/**
 * The documents themselves, each bound to its own source and version.
 *
 * Call sites ask for `TERMS_DOC` or `PRIVACY_DOC` rather than importing
 * sections and a version separately and pairing them up by hand — which is the
 * mistake that ends with a document rendering someone else's version number.
 */

import {
  SECTIONS as TERMS_SECTIONS, TERMS_VERSION, TERMS_UPDATED,
} from './terms'
import {
  SECTIONS as PRIVACY_SECTIONS, COOKIE_SECTIONS,
  PRIVACY_VERSION, PRIVACY_UPDATED, COOKIE_POLICY_VERSION,
} from './privacy'

export const TERMS_DOC = {
  key: 'terms',
  title: 'Terms of Service',
  path: '/terms',
  sections: TERMS_SECTIONS,
  version: TERMS_VERSION,
  updated: TERMS_UPDATED,
}

export const PRIVACY_DOC = {
  key: 'privacy',
  title: 'Privacy Notice',
  path: '/privacy',
  sections: PRIVACY_SECTIONS,
  version: PRIVACY_VERSION,
  updated: PRIVACY_UPDATED,
}

/** The cookie policy on its own — the same section that appears as section 9
 *  of the privacy notice, for the /cookies page and the banner's policy link. */
export const COOKIE_DOC = {
  key: 'cookies',
  title: 'Cookie Policy',
  path: '/cookies',
  sections: COOKIE_SECTIONS,
  version: COOKIE_POLICY_VERSION,
  updated: PRIVACY_UPDATED,
}

/** The two documents a new account must be shown, in the order they are shown.
 *  Registration walks this list, so adding a third document here is all it
 *  takes to put one into the sign-up flow. */
export const CONSENT_DOCS = [TERMS_DOC, PRIVACY_DOC]
