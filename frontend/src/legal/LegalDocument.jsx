/**
 * Renders a legal document from the structured source in ./terms.js or
 * ./privacy.js. Used by the sign-up modal, the read-only modal in the profile
 * and the standalone pages, so none of them can diverge from the others.
 *
 * The section shape is: { id, heading, lead?, paragraphs?, bullets?, table?,
 * subsections?, after? }. Every key is optional but `heading`, and they render
 * in that order.
 */

function SectionBody({ s }) {
  return (
    <>
      {s.lead && <p className="legal-lead">{s.lead}</p>}

      {s.paragraphs?.map((p, i) => <p key={i}>{p}</p>)}

      {s.bullets && (
        <ul>
          {s.bullets.map((b, i) => <li key={i}>{b}</li>)}
        </ul>
      )}

      {s.table && (
        // Three columns of prose do not fit a phone, so the table scrolls
        // sideways in its own box rather than forcing the page to.
        <div className="legal-table-wrap">
          <table className="legal-table">
            <thead>
              <tr>{s.table.columns.map(c => <th key={c}>{c}</th>)}</tr>
            </thead>
            <tbody>
              {s.table.rows.map((row, i) => (
                <tr key={i}>{row.map((cell, j) => <td key={j}>{cell}</td>)}</tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* One level of nesting, which the cookie policy needs so it can sit
          inside the privacy notice and also stand alone at /cookies. Deeper
          nesting is not supported deliberately: a legal document that needs
          three levels of heading needs rewriting, not a better renderer. */}
      {s.subsections?.map(sub => (
        <section key={sub.id} id={sub.id} className="legal-subsection">
          <h4>{sub.heading}</h4>
          <SectionBody s={sub} />
        </section>
      ))}

      {s.after && <p>{s.after}</p>}
    </>
  )
}

export default function LegalDocument({ sections, version, updated }) {
  return (
    <div className="legal-doc">
      {version && (
        <p className="legal-updated">
          Version {version}{updated ? ` · Last updated ${updated}` : ''}
        </p>
      )}

      {sections.map(s => (
        <section key={s.id} id={s.id} className="legal-section">
          <h3>{s.heading}</h3>
          <SectionBody s={s} />
        </section>
      ))}
    </div>
  )
}
