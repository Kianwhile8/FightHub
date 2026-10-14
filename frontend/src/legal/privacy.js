// The Privacy Notice, as data rather than markup, so the same source renders
// in the sign-up modal, on the standalone /privacy page and in the profile
// without the three drifting apart.
//
// PRIVACY_VERSION and COOKIE_POLICY_VERSION must match the constants of the
// same names in app/legal.py. The backend stores the version a user was shown;
// this file is the wording that version refers to. Bump both together, and only
// for changes of substance — see app/legal.py.
//
// Split out of the combined terms document at version 2026-09-19. CONTROLLER is
// imported from ./terms.js rather than duplicated, so the contact address
// cannot be corrected in one document and left stale in the other.

import { CONTROLLER, MINIMUM_AGE, DOMAIN_NOTE } from './terms'

export const PRIVACY_VERSION = '2026-10-03'
export const PRIVACY_UPDATED = '3 October 2026'
export const COOKIE_POLICY_VERSION = '2026-09-19'

export { CONTROLLER, MINIMUM_AGE }

// The cookie section is exported on its own as well as within SECTIONS, so the
// /cookies page and the banner's "read the policy" link can show just the
// cookie policy without reproducing the whole notice around it. One source
// either way.
export const COOKIE_SECTIONS = [
  {
    id: 'cookies-what',
    heading: 'What we set',
    lead: 'FightHub sets one cookie. That is the whole list:',
    table: {
      columns: ['Cookie', 'Purpose', 'Expires', 'Category'],
      rows: [
        [
          'session',
          'Keeps you signed in between page loads. It holds a signed reference to your account and nothing else — no personal data is stored in the cookie itself.',
          '8 hours, or when you sign out',
          'Strictly necessary',
        ],
      ],
    },
    after: 'It is a first-party cookie, set by FightHub itself. It is marked HttpOnly, so scripts cannot read it, SameSite=Lax, so it is not sent on requests originating from other sites, and Secure in production, so it is only ever transmitted over HTTPS.',
  },
  {
    id: 'cookies-not',
    heading: 'What we do not set',
    bullets: [
      'No analytics or statistics cookies. We do not use Google Analytics or any equivalent.',
      'No advertising, marketing or re-targeting cookies. We carry no advertising.',
      'No third-party cookies of any kind. The site loads no external scripts, fonts, trackers or embedded content, so no other party is in a position to set one.',
      'No cross-site tracking, device fingerprinting or profiling.',
    ],
  },
  {
    id: 'cookies-consent',
    heading: 'Your choice, and why the essential cookie has no off switch',
    paragraphs: [
      'Under the Privacy and Electronic Communications Regulations, consent is required for cookies that are not strictly necessary for a service you have asked for. Our session cookie is strictly necessary — without it the platform cannot tell one signed-in user from another — so it is set on the basis of that exemption rather than on consent.',
      'The cookie banner therefore lists it as always active. That is not a dark pattern: it is an honest statement that declining it would mean declining the ability to sign in. The banner also lists an analytics category and a marketing category, both switched off and both disabled, because we do not currently use either. If that ever changes, those toggles become live, they will remain off until you turn them on, and nothing will be set before you do.',
      'Your choice is recorded in your browser\'s local storage rather than in a cookie, and it never leaves your device. You can change or withdraw it at any time from Cookie preferences in your profile. Clearing your browser data clears the record, and the banner will ask again.',
      'If we materially change what cookies we set, the stored choice is invalidated and you will be asked again.',
    ],
  },
]

export const SECTIONS = [
  {
    id: 'who',
    heading: 'Who we are, and what this notice covers',
    paragraphs: [
      `${CONTROLLER.name} is the controller of the personal data described here. This notice explains what we collect, why, how long we keep it, who can see it, and what you can do about it. It forms part of the Terms of Service and applies to everyone who holds an account.`,
      `You can contact us about anything in this notice at ${CONTROLLER.contact}. We will respond within one month.`,
      `You must be at least ${MINIMUM_AGE} to hold an account. If you are under 18, a parent, guardian or registered coach must agree to your account and should read this notice with you.`,
      DOMAIN_NOTE,
    ],
  },
  {
    id: 'data-collected',
    heading: '1. What personal data we hold',
    lead: 'We collect only what the platform needs to work:',
    table: {
      columns: ['Data', 'Why we hold it', 'Lawful basis'],
      rows: [
        ['Email address and password (stored only as a salted hash — we never see or store your actual password)', 'To create your account, sign you in and contact you about your account', 'Performance of a contract'],
        ['Role (fighter, coach or promoter)', 'To decide what you are allowed to do on the platform', 'Performance of a contract'],
        ['Gender, where you are a fighter and choose to state it', 'Combat sports are contested in single-sex divisions, so this is what allows a fighter to be paired safely — and what prevents a mixed pairing being offered. You may decline to answer; matchmaking then simply never offers your profile a pairing on that basis. It is asked only of fighters, and is not collected from coaches or promoters at all.', 'Performance of a contract'],
        ['Fighter profile: name, date of birth, weight, discipline, gym, county, description, photograph', 'To build the profile and to pair you safely with comparable opponents', 'Performance of a contract; consent for the photograph'],
        ['Competitive record: results, rating, bout history, opponents, prior experience in other disciplines, event registrations', 'To maintain your record, produce rankings and generate matchmaking suggestions', 'Performance of a contract'],
        ['Billing data, where your account holds a subscription: plan, trial and subscription status, trial-end and billing-period dates, and Stripe’s reference for your customer and subscription records', 'To determine what your account is entitled to do, and to let you manage your subscription from the billing page', 'Performance of a contract'],
        ['Technical data: session cookie, IP address, server logs', 'To keep you signed in, to rate-limit sign-in attempts and to investigate abuse and faults', 'Legitimate interests — keeping the service available and secure'],
        ['Record of your acceptance of the terms and of this notice: version and timestamp', 'To evidence that agreement was given and that you were informed, as data protection law requires', 'Legal obligation'],
        ['Account deletion requests: the request, its date, any reason you give, and the date it was actioned', 'To action your erasure request and to evidence that we did so within the time the law allows', 'Legal obligation'],
      ],
    },
    after: 'We do not collect anything we have no use for. There is no marketing profile, no advertising identifier, no behavioural tracking, and no data collected "in case it is useful later". We do not sell your data and we do not share it with advertisers.',
  },
  {
    id: 'visibility',
    heading: '2. What other people can see',
    lead: 'This is the section worth reading twice, because a fighter profile is published by design.',
    paragraphs: [
      'If you create a fighter profile, the following is visible to every signed-in user of FightHub: your fighter name, your age (derived from your date of birth — the date itself is not shown), your weight and weight class, your gender where you have stated one, your discipline, your gym, your county, anything you write in your profile description, your profile photograph, your win/loss/draw record, your rating and ranking, and your bout history including the names of your opponents.',
      'Your email address, your password, your account role, your IP address and your account-level gender answer are never shown to other users. Administrators can see email addresses in order to operate the platform.',
      'You can limit this. The "hide my record" control in your profile withholds your win/loss/draw record and your fight history from other users, and takes you out of matchmaking suggestions so you are not proposed as an opponent.',
      'It does not make your profile invisible. Your name, age, weight, gym and county still appear in fighter listings and on the rankings page, because other fighters and coaches need to know who trains where. What is withheld is your results. If you want your profile gone entirely, ask us to delete it — see section 6.',
      'Coaches can see the profiles of fighters at their gym. Promoters can see the profiles of fighters registered for their events. Neither can see your email address.',
      'Nothing on FightHub is visible to people without an account, and no part of the platform is indexed by search engines.',
    ],
  },
  {
    id: 'photos',
    heading: '3. Photographs',
    paragraphs: [
      'Profile and event photographs are stored in private cloud storage and served through the platform to signed-in users. They are not published to the open web and are not indexed by search engines.',
      'Only upload a photograph you have the right to use. If it shows someone other than you, you need their agreement first.',
      'A photograph is the one item here we rely on your consent for, which means you can withdraw it at any time by deleting the photograph from your profile. Doing so removes it from storage.',
    ],
  },
  {
    id: 'sharing',
    heading: '4. Who else processes your data',
    paragraphs: [
      'We use no analytics provider, no advertising network, no customer-messaging tool and no error-reporting service. The platform loads nothing from any external server while you are using it — the only point at which a third party is involved is if you subscribe, described below.',
      'The processor we use to run the application is Google Cloud Platform, which hosts the application, the database and uploaded photographs under a data processing agreement. Data is held in the London region (europe-west2), in the United Kingdom.',
      'If you take out a subscription, payment is handled by Stripe. Your card details are entered directly into Stripe’s own checkout page and go straight to Stripe — we never see or store them. Stripe receives your email address and the plan you are subscribing to, and gives back to us only a customer reference, a subscription reference, its status, and the dates your current billing period runs between, which is the billing data listed in section 1. Stripe acts as an independent controller of the payment data it holds, under its own privacy notice, published at stripe.com/privacy.',
      'We will disclose personal data to a third party outside these arrangements only where we are legally required to — a court order, or a lawful request from a public authority — and we will tell you when that happens unless we are prohibited from doing so.',
    ],
  },
  {
    id: 'retention',
    heading: '5. How long we keep it',
    bullets: [
      'Account and profile data: for as long as your account is open.',
      'Billing data: for as long as your subscription is active, plus any period Stripe or we need afterward to resolve a payment, a chargeback or a tax obligation.',
      'After your account is deleted: personal data is removed within 30 days. Bout results remain on your opponents’ records in anonymised form, as described in section 4 of the Terms of Service.',
      'Server and security logs: 90 days.',
      'Record of your acceptance of the terms and this notice, and of any deletion request: kept for six years after the account closes, because it is the evidence that we obtained agreement and honoured your rights. This is the one thing a deletion request does not erase, and the law requires us to keep it.',
    ],
  },
  {
    id: 'rights',
    heading: '6. Your rights, and how to use them',
    lead: 'Under the UK GDPR you have the right to:',
    bullets: [
      'Be told what personal data we hold about you, and get a copy of it.',
      'Have inaccurate data corrected — most of it you can edit yourself from your profile.',
      'Have your data erased.',
      'Restrict or object to how we use your data, including our use of it under legitimate interests.',
      'Receive your data in a portable, machine-readable format.',
      'Withdraw consent at any time where consent is the basis we rely on — for example by removing your profile photograph. Withdrawing consent does not affect processing that already happened.',
      'Complain to the Information Commissioner’s Office at ico.org.uk. We would rather you came to us first, but you do not have to.',
    ],
    after: `To exercise any of these, use the controls in your profile where they exist, or contact us at ${CONTROLLER.contact}.`,
  },
  {
    id: 'deletion',
    heading: '7. Deleting your account',
    paragraphs: [
      'You can ask for your account and your personal data to be deleted at any time, from Request account deletion in your profile. You do not have to give a reason, and we will not ask you for one.',
      'The request goes to an administrator rather than taking effect the instant you click. There are two reasons for that, and both are in your interest: a deletion reaches into other people’s competitive records and has to be carried out correctly, and an account that has been taken over by someone else should not be able to destroy the real owner’s history in a single click. The trade-off is that erasure is not immediate.',
      'We will complete it within 30 days, which is the outer limit the law allows, and in practice sooner. While a request is pending you can cancel it yourself from the same place. We will contact you at your registered email address if we need anything to action it, and if we refuse it — which we would only do where the law permits, such as a request made by someone who is not the account holder — we will tell you why and remind you of your right to complain to the ICO.',
    ],
    after: 'What deletion removes: your account, your email address, your password hash, your fighter profiles, your competitive record, your prior-experience entries, your event registrations and your uploaded photographs. If you hold an active subscription, it is cancelled with Stripe before the account is removed, so you are not billed again. What it leaves: bout results on your opponents’ records, anonymised so they no longer identify you, and the dated record that you accepted the terms and asked for deletion, which we are required to keep for six years.',
  },
  {
    id: 'security',
    heading: '8. Where your data is held and how it is protected',
    paragraphs: [
      'FightHub runs on Google Cloud Platform in the London region (europe-west2), so your data is stored in the United Kingdom. Google Cloud acts as our processor under a data processing agreement.',
      'Traffic is encrypted in transit with HTTPS. Passwords are stored only as salted hashes and cannot be reversed. Sign-in attempts are rate-limited to frustrate password guessing. Access to the production database is restricted to administrators, and secrets are held in a managed secret store rather than in the application’s source code. Databases are backed up daily.',
      'No system is perfectly secure. If a breach occurs that is likely to put your rights at risk, we will tell you and the Information Commissioner’s Office without undue delay, and in any event within 72 hours of becoming aware of it.',
    ],
  },
  {
    id: 'cookies',
    heading: '9. Cookie Policy',
    lead: 'The short version: one strictly necessary session cookie, nothing else, no tracking of any kind. In full:',
    // Rendered as sub-sections by the document renderer.
    subsections: COOKIE_SECTIONS,
  },
  {
    id: 'changes',
    heading: '10. Changes to this notice',
    paragraphs: [
      'If we change this notice in a way that affects how we use your data, we will ask you to acknowledge the new version the next time you sign in, and we will say what changed. Minor corrections that do not change the substance will not trigger a new prompt.',
      `This version is dated ${PRIVACY_UPDATED}. The Terms of Service are versioned separately.`,
    ],
  },
]
