import { Link } from 'react-router-dom'
import { PLANS, TRIAL_DAYS } from '../constants/pricing'

// The public landing page. Rendered outside Layout, so it carries its own nav
// and footer rather than the signed-in sidebar.
//
// This page calls no API, on purpose. /api/stats and the rankings are all
// @login_required and would 401 for the visitor this page exists to convince,
// and an anonymous page is the worst place to spend the 400/hour limiter
// budget. Everything here is static copy.
//
// It also loads nothing from any external origin — no web fonts, no images, no
// third-party scripts. Feature 7 below promises exactly that, and a landing
// page that broke the promise it makes in its own copy would be the one bug
// nobody could argue was minor.

const PROBLEMS = [
  'A coach messages six other coaches to find one opponent who is the right weight, the right experience, and actually free that weekend — one home show can eat an evening a week for a month, just on matchmaking.',
  "Records live in somebody's notes app, a WhatsApp thread or an unofficial database that is only as good as whoever last updated it. The record a fighter gives you and the record a fighter has are not always the same number.",
  "Weight 'allowances' get stretched by a kilo or two on the day, and undeclared bouts in another discipline surface only after the bell — by which point a debut has been matched against years of hidden experience.",
  'Nobody can say how a 4-0 kickboxer compares to a 2-1 MMA fighter, so a debut gets matched against someone with eleven bouts and it shows in the first thirty seconds.',
  'A late pull-out voids weeks of preparation, and the replacement is found with days to spare instead of weeks. The card is built in a spreadsheet, reordered in a group chat, and printed wrong on the night.',
]

const SOLUTIONS = [
  'One record per fighter, across four disciplines, kept by the gym that trains them — not re-typed into a group chat every time a show is announced.',
  'A rating computed from results that were actually logged — not from a record that was claimed.',
  'Weight and recorded experience built into the match score itself, so a lopsided pairing has to be deliberately overridden rather than quietly waved through.',
  'Opponent suggestions scored on weight, experience, activity and rating, with same-sex pairing enforced in the algorithm rather than offered as a filter.',
  'A drag-and-drop running order with a bout limit you set, settled before the posters go out.',
]

const EVIDENCE_STATS = [
  { val: '88.5', lbl: 'System Usability Scale score — "excellent" starts at 80.3' },
  { val: '100%', lbl: 'of evaluation tasks completed by every participant' },
  { val: '12', lbl: 'coaches and fighters interviewed before any of this was built' },
]

const BANDS = [
  ['Amateur', 'band-amateur'],
  ['Prospect', 'band-prospect'],
  ['Contender', 'band-contender'],
  ['Regional', 'band-regional'],
  ['Elite', 'band-elite'],
]

const FEATURES = [
  {
    title: 'Ratings that mean something',
    body: 'Every result moves a fighter’s Elo. Wins over higher-rated opponents count for more, finishes count for more than decisions, and staying active counts for something too. Five bands, so you can read a fighter’s level without reading their whole record.',
    bands: true,
  },
  {
    title: 'Matchmaking that argues with you',
    body: 'Ask for opponents for any fighter and get a ranked list: a match score, the weight difference in kilograms, their rating and band, and how many bouts of real experience they have. Pairings that fail the experience gap are held back by default and shown flagged, with the reason, when you ask to see them.',
  },
  {
    title: 'Segregated by design, not by checkbox',
    body: 'Combat sports are contested in single-sex divisions. FightHub treats that as a rule inside the matchmaker, not a filter somebody can forget to tick. The minimum age for an account is 16.',
  },
  {
    title: 'Experience carries between sports',
    body: 'A fighter with nine kickboxing bouts is not a debutant in MMA. Link a profile across disciplines, or declare prior experience directly on the profile, and it is carried into the matching as transferred bouts — so an experienced striker is never matched like a novice.',
  },
  {
    title: 'Rosters the coach actually controls',
    body: 'A gym’s fighters belong to the gym. You add, edit and log results for your own roster, and nobody can quietly pull a fighter off it onto theirs — a transfer needs the current coach to release them first. Search unattached fighters across every discipline when you are filling a roster.',
  },
  {
    title: 'Fight cards without the spreadsheet',
    body: 'Create the event and its venue in one step, register fighters, build the card, set a bout limit, and drag the running order into place with the main event on top. Mark bouts complete on the night and the result lands on both fighters’ records, attributed to the event.',
  },
  {
    title: 'Privacy is a switch, not a request',
    body: 'Any fighter can hide their competitive record from a single toggle. Their results and their standing are then withheld from everyone else, and they drop out of matchmaking. Email addresses are never shown to other users. No analytics, no advertising, no third-party scripts and no external fonts — the page you are reading loads nothing from anywhere else.',
  },
]

const STEPS = [
  {
    title: 'Create your account',
    body: `Pick fighter, coach or promoter. The ${TRIAL_DAYS}-day trial starts there and then — no card.`,
  },
  {
    title: 'Add your gym and your fighters',
    body: 'Or claim the profile that already exists for you, in every discipline you compete in.',
  },
  {
    title: 'Run it',
    body: 'Log results, read the rankings, pull up opponents, build the card.',
  },
]

const FAQS = [
  {
    q: 'What happens when the trial ends?',
    a: 'Your account stays and so does everything in it. You can still read the fighter database, the rankings and your own record. Adding, editing and matchmaking need a subscription.',
  },
  {
    q: 'Do you take a cut of anything?',
    a: 'No. No per-event fee and no commission on any bout arranged through the platform.',
  },
  {
    q: 'Where is my data held?',
    a: 'The United Kingdom — Google Cloud, London region. The detail is in the Privacy Notice.',
  },
  {
    q: 'Can I cancel?',
    a: 'Yes, from your billing page, whenever you like. Access runs to the end of the period you paid for.',
  },
]

export default function Landing() {
  return (
    <div className="lp">
      <header className="lp-nav">
        <div className="lp-container lp-nav-inner">
          <div className="lp-logo">
            Fight<span>Hub</span>
          </div>
          <nav className="lp-nav-actions">
            <a className="lp-nav-link" href="#pricing">Pricing</a>
            <Link className="btn btn-sm" to="/login">Sign in</Link>
            <Link className="btn btn-sm btn-primary" to="/login?tab=register">Create account</Link>
          </nav>
        </div>
      </header>

      <main>
        {/* ── Hero ───────────────────────────────────────────────────────── */}
        <section className="lp-hero">
          <div className="lp-container">
            <div className="lp-hero-eyebrow">Amateur combat sports · England</div>
            <h1 className="lp-hero-title">Stop matchmaking from a group chat.</h1>
            <p className="lp-hero-sub">
              FightHub is the record book, the ranking system and the fight-card
              builder for amateur MMA, boxing, kickboxing and Muay Thai. Every
              fighter&rsquo;s real record, every gym&rsquo;s roster, every bout on your
              card — in one place, with the safety checks built into the matching
              rather than left to memory.
            </p>
            <div className="lp-hero-actions">
              <Link className="btn btn-primary" to="/login?tab=register">
                Start your {TRIAL_DAYS}-day free trial
              </Link>
              <Link className="btn" to="/login">Sign in</Link>
            </div>
            <p className="lp-hero-note">
              {PLANS.pro.price} a year for coaches and promoters.{' '}
              {PLANS.fighter.price} a year for fighters. No card needed to start
              the trial.
            </p>
          </div>
        </section>

        {/* ── Problem / solution ─────────────────────────────────────────── */}
        <section className="lp-section lp-section--alt">
          <div className="lp-container">
            <div className="lp-split">
              <div className="lp-split-col">
                <h2 className="lp-split-title">How amateur matchmaking works today</h2>
                <ul className="lp-split-list lp-split-list--problem">
                  {PROBLEMS.map((p, i) => <li key={i}>{p}</li>)}
                </ul>
              </div>
              <div className="lp-split-col">
                <h2 className="lp-split-title">What FightHub does instead</h2>
                <ul className="lp-split-list lp-split-list--solution">
                  {SOLUTIONS.map((s, i) => <li key={i}>{s}</li>)}
                </ul>
              </div>
            </div>
          </div>
        </section>

        {/* ── Evidence ───────────────────────────────────────────────────── */}
        <section className="lp-section" id="evidence">
          <div className="lp-container">
            <div className="lp-section-head">
              <h2 className="lp-section-title">Built from research, not guesswork</h2>
              <p className="lp-section-lead">
                This wasn&rsquo;t designed in a vacuum. Structured interviews with
                coaches and fighters across boxing, kickboxing, MMA and BJJ
                shaped every feature above, the matchmaking algorithm was
                tuned to answer what they described, and the finished
                platform was then handed back to real coaches and fighters to
                put through a full task-based evaluation.
              </p>
            </div>
            <div className="lp-evidence-stats">
              <div className="stat-grid">
                {EVIDENCE_STATS.map(s => (
                  <div className="stat" key={s.lbl}>
                    <div className="stat-val">{s.val}</div>
                    <div className="stat-lbl">{s.lbl}</div>
                  </div>
                ))}
              </div>
            </div>
            <p className="lp-evidence-note">
              Feedback from that evaluation — on bout-count gating, loss
              penalties and a trust signal for unreliable records — is
              already shaping what gets built next.
            </p>
          </div>
        </section>

        {/* ── Features ───────────────────────────────────────────────────── */}
        <section className="lp-section lp-section--alt">
          <div className="lp-container">
            <div className="lp-section-head">
              <h2 className="lp-section-title">What you actually get</h2>
              <p className="lp-section-lead">
                Built for amateur shows in England, across four disciplines, by
                someone who got tired of the spreadsheet.
              </p>
            </div>
            <div className="lp-grid">
              {FEATURES.map(f => (
                <div className="card lp-feature" key={f.title}>
                  <h3 className="lp-feature-title">{f.title}</h3>
                  <p className="lp-feature-body">{f.body}</p>
                  {/* The real rank pills from the rankings page, not a picture
                      of them — same classes, so they can never drift. */}
                  {f.bands && (
                    <div className="lp-feature-bands">
                      {BANDS.map(([label, cls]) => (
                        <span className={`band-pill ${cls}`} key={cls}>{label}</span>
                      ))}
                    </div>
                  )}
                </div>
              ))}
            </div>
          </div>
        </section>

        {/* ── How it works ───────────────────────────────────────────────── */}
        <section className="lp-section">
          <div className="lp-container">
            <div className="lp-section-head">
              <h2 className="lp-section-title">How it works</h2>
            </div>
            <ol className="lp-steps">
              {STEPS.map((s, i) => (
                <li className="lp-step" key={s.title}>
                  <div className="lp-step-num">{i + 1}</div>
                  <div>
                    <h3 className="lp-step-title">{s.title}</h3>
                    <p className="lp-step-body">{s.body}</p>
                  </div>
                </li>
              ))}
            </ol>
          </div>
        </section>

        {/* ── Pricing ────────────────────────────────────────────────────── */}
        <section className="lp-section lp-section--alt" id="pricing">
          <div className="lp-container">
            <div className="lp-section-head">
              <h2 className="lp-section-title">Priced so any gym can afford it</h2>
              <p className="lp-section-lead">
                One flat yearly fee. No per-event charge, no commission, no
                per-fighter pricing that punishes you for having a big room.
              </p>
            </div>
            <div className="lp-plans">
              <PlanCard plan={PLANS.pro} featured />
              <PlanCard plan={PLANS.fighter} />
            </div>
            <p className="lp-plan-note">
              Both billed annually in GBP. {TRIAL_DAYS} days free first. Cancel any
              time — you keep access to the end of the period you have paid for.
              Reading the database, the rankings and your own record stays
              available whether you subscribe or not.
            </p>
          </div>
        </section>

        {/* ── FAQ ────────────────────────────────────────────────────────── */}
        <section className="lp-section">
          <div className="lp-container">
            <div className="lp-section-head">
              <h2 className="lp-section-title">Questions</h2>
            </div>
            <div className="lp-faq">
              {FAQS.map(f => (
                <div className="lp-faq-item" key={f.q}>
                  <h3 className="lp-faq-q">{f.q}</h3>
                  <p className="lp-faq-a">{f.a}</p>
                </div>
              ))}
            </div>
          </div>
        </section>

        {/* ── Final CTA ──────────────────────────────────────────────────── */}
        <section className="lp-cta">
          <div className="lp-container">
            <h2 className="lp-cta-title">Put your gym&rsquo;s record straight.</h2>
            <p className="lp-cta-sub">
              {TRIAL_DAYS} days, every feature, no card.
            </p>
            <Link className="btn btn-primary" to="/login?tab=register">
              Create your account
            </Link>
          </div>
        </section>
      </main>

      <footer className="lp-footer">
        <div className="lp-container">
          <div className="lp-logo lp-logo--sm">Fight<span>Hub</span></div>
          <nav className="lp-footer-links">
            <Link to="/terms">Terms of Service</Link>
            <Link to="/privacy">Privacy Notice</Link>
            <Link to="/cookies">Cookie Policy</Link>
            <Link to="/login">Sign in</Link>
          </nav>
          <p className="lp-footer-note">
            Record-keeping and matchmaking for amateur combat sports. Not a
            substitute for your governing body, your coach, or a medical
            professional.
          </p>
        </div>
      </footer>
    </div>
  )
}

function PlanCard({ plan, featured }) {
  return (
    <div className={`card lp-plan${featured ? ' lp-plan--featured' : ''}`}>
      {featured && <div className="lp-plan-flag">Most gyms</div>}
      <h3 className="lp-plan-name">{plan.name}</h3>
      <div className="lp-plan-priceline">
        <span className="lp-plan-price">{plan.price}</span>
        <span className="lp-plan-period">{plan.period}</span>
      </div>
      <p className="lp-plan-for">{plan.for}</p>
      <ul className="lp-plan-list">
        {plan.features.map(f => <li key={f}>{f}</li>)}
      </ul>
      <Link
        className={`btn ${featured ? 'btn-primary' : ''} lp-plan-cta`}
        to="/login?tab=register"
      >
        Start free trial
      </Link>
    </div>
  )
}
