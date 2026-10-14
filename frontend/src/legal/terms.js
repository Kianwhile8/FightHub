// The Terms of Service, as data rather than markup, so the same source renders
// in the sign-up modal and on the standalone /terms page without the two
// drifting apart.
//
// TERMS_VERSION must match TERMS_VERSION in app/legal.py. The backend stores
// the version a user accepted; this file is the wording that version refers to.
// Bump both together, and only for changes of substance — see app/legal.py.
//
// The privacy notice lives in ./privacy.js. The two were a single combined
// document until version 2026-09-19; they were separated because they do
// different jobs — this one is the contract between the user and FightHub, the
// other is the disclosure required by UK GDPR Art. 13 — and because a change
// to one should not force re-agreement to the other.

import { TRIAL_DAYS } from '../constants/pricing'

export const TERMS_VERSION = '2026-10-03'
export const TERMS_UPDATED = '3 October 2026'
export const MINIMUM_AGE = 16

// TODO(URGENT — before any real user outside the project relies on this):
// `contact` is still the placeholder it was created with. It is the address a
// data-subject access request, an erasure request or an ICO complaint gets
// sent to under sections 1 and 6 of the Privacy Notice below, so a placeholder
// here means those requests currently go nowhere. Replace it with a real
// inbox the operator actually reads — it does not need to be @fighthub.co.uk,
// any monitored address will do until that domain exists — and bump
// TERMS_VERSION / PRIVACY_VERSION (here and in app/legal.py) when it changes,
// since the version is what the backend uses to know who needs re-prompting.
export const CONTROLLER = {
  name: 'FightHub',
  contact: 'privacy@fighthub.example',
}

// Shown in both documents (imported into privacy.js) so the two can't drift.
// TODO: remove this once the service has actually moved to fighthub.co.uk (or
// whatever domain is registered) and bump both version constants when it does
// — a domain move is exactly the kind of change clause 8 below promises to
// flag.
export const DOMAIN_NOTE = 'FightHub is currently in testing and runs from a temporary address provided by our hosting platform (Google Cloud) while a permanent fighthub.co.uk domain is registered. Moving to that domain will not change who operates the service, these terms, your account, or how your data is handled — we will say so here if anything about that ever does change.'

export const SECTIONS = [
  {
    id: 'summary',
    heading: 'The short version',
    lead: 'This summary is not a substitute for the full terms below, but nothing below contradicts it.',
    bullets: [
      'FightHub is a record-keeping and matchmaking tool for amateur combat sports. It is not a substitute for your governing body, your coach, or a medical professional.',
      `New accounts get a ${TRIAL_DAYS}-day free trial with no card required. After it, adding or editing fighters, logging results, running matchmaking and building fight cards needs a paid subscription; reading the fighter database, the rankings and your own profile and record stays free whether or not you subscribe.`,
      'If you create a fighter profile, other signed-in users can see it — including your name, age, weight, gym, county and full competitive record. That visibility is the point of the platform.',
      'Your email address is never shown to other users. Only administrators can see it.',
      'You can hide your competitive record at any time from your profile. Your win/loss record and fight history are then withheld from other users, and you are left out of matchmaking.',
      'You can ask us to delete your account and your data at any time, and you do not have to give a reason. How that works is set out in the Privacy Notice.',
      DOMAIN_NOTE,
    ],
  },
  {
    id: 'eligibility',
    heading: '1. Who can use FightHub',
    paragraphs: [
      'You must be at least 16 years old to hold an account. If you are under 18, you may only create an account and publish a fighter profile with the agreement of a parent, guardian or registered coach, who is responsible for reviewing these terms with you.',
      'You must give accurate information when you register. Fight records, weights, dates of birth and gender are used to pair fighters with each other, and false information in any of those fields creates a real risk of physical harm to you and to your opponent. Deliberately misstating them is a breach of these terms and we may remove the account.',
      'You are responsible for keeping your password secret and for anything done through your account.',
    ],
  },
  {
    id: 'cost',
    heading: '2. What it costs',
    paragraphs: [
      `Every new account gets a ${TRIAL_DAYS}-day free trial with full access and no card required.`,
      'After the trial, continuing to add or edit fighters, log results, use matchmaking, or create events and fight cards needs an active paid subscription. Reading the fighter database, the rankings and your own profile and record remains available whether or not you subscribe. There is no per-event fee and no commission on any bout arranged through the platform, and the price for each role is shown on the billing page before you are asked to pay anything.',
      'Payment is handled by Stripe. We never see or store your card details — they are entered directly into Stripe’s own checkout and processed under Stripe’s terms, not ours. Section 4 of the Privacy Notice sets out what Stripe receives and what it returns to us.',
      'You can cancel a subscription at any time from your billing page. Cancelling stops future renewals; access continues to the end of the period you have already paid for, and no further payment is taken.',
      'We do not sell your data and we do not carry advertising. Subscription revenue is the only way FightHub is funded.',
    ],
  },
  {
    id: 'conduct',
    heading: '3. Acceptable use',
    lead: 'You agree not to:',
    bullets: [
      'Create a profile for another person without their knowledge and agreement, or impersonate anyone.',
      'Upload photographs of other people without their permission, or any image you do not hold the rights to.',
      'Post content that is abusive, harassing, discriminatory, defamatory or unlawful.',
      'Scrape, bulk-download or republish other users’ profiles or records.',
      'Attempt to gain access to accounts, data or systems that are not yours, or to disrupt the service for others.',
    ],
    after: 'We may suspend or remove an account that breaches this section. Where we do, we will tell you why unless we are legally prevented from doing so.',
  },
  {
    id: 'records',
    heading: '4. Records, rankings and matchmaking',
    paragraphs: [
      'Results, ratings and rankings are generated from data entered by fighters, coaches, promoters and administrators. We do not independently verify them, and they carry no official standing with any sanctioning body.',
      'Matchmaking suggestions are produced automatically from rating, weight, age, gender and recorded experience. Fighters are only ever paired within the same gender, and a pairing is refused outright where the two differ. They are suggestions only. No bout is ever agreed, sanctioned or made safe by this platform — that decision rests with you, your coach, the promoter and the relevant governing body.',
      'Because a competitive record is a shared history, a bout result involves two fighters. If your account is deleted, results already recorded against your opponents remain part of their record, but are anonymised so that they no longer identify you.',
    ],
  },
  {
    id: 'cookies',
    heading: '5. Cookies',
    paragraphs: [
      'FightHub sets one cookie: a session cookie that keeps you signed in. It is strictly necessary for the service to work, expires after 8 hours, and is not used for analytics, tracking or advertising. We set no third-party cookies and use no advertising or analytics services.',
      'Because the session cookie is strictly necessary, it cannot be switched off while you are using the platform — without it we cannot tell one signed-in user from another. The cookie banner therefore shows it as always active, and the optional categories it lists are unused and switched off.',
      'The full Cookie Policy, including what the cookie contains and how long it lasts, forms part of the Privacy Notice and can be read there or at the /cookies page. You can change or review your cookie choice at any time from Cookie preferences in your profile.',
    ],
  },
  {
    id: 'data',
    heading: '6. Your data',
    paragraphs: [
      'How we collect, use, share and retain personal data, what other users can see, how long we keep it, and what rights you have over it are all set out in the Privacy Notice, which forms part of these terms. Please read it: section 5 of that notice, on what other people can see, is the one most worth reading twice.',
      'In short: we collect only what the platform needs to work, we do not sell it, we do not share it with advertisers, and we do not use it to profile you for marketing.',
    ],
  },
  {
    id: 'liability',
    heading: '7. Liability',
    paragraphs: [
      'Combat sports are inherently dangerous. FightHub is a record-keeping and administrative tool. It does not sanction bouts, assess medical fitness, verify results or supervise competition, and it is not responsible for injury arising from any bout, however that bout was arranged.',
      'The service is provided as-is. We do not guarantee that it will be uninterrupted, or that records and ratings are accurate or complete.',
      'Nothing in these terms limits liability for death or personal injury caused by our negligence, for fraud, or for anything else that cannot lawfully be limited.',
    ],
  },
  {
    id: 'changes',
    heading: '8. Changes to these terms',
    paragraphs: [
      'If we change these terms in a way that affects your rights, we will ask you to accept the new version the next time you sign in, and we will say what changed. Minor corrections that do not change the substance will not trigger a new prompt.',
      'The Privacy Notice is versioned separately, for the same reason and on the same basis.',
      `This version is dated ${TERMS_UPDATED}. These terms are governed by the law of England and Wales.`,
    ],
  },
]
