import Link from "next/link";

export default function HomePage() {
  return (
    <>
      <section className="hero">
        <h1>Know before you submit.</h1>
        <p>
          ZGrader is an independent pre-grading service for trading card games. Send us your
          cards, and we&apos;ll scan and analyze centering, corners, edges, and surface, then
          show you exactly how PSA, BGS, CGC, and TAG are likely to treat each one before you pay
          to submit for real.
        </p>
        <div className="hero-actions">
          <Link href="/register" className="btn">
            Get started
          </Link>
          <Link href="/login" className="btn btn-secondary">
            Log in
          </Link>
        </div>
      </section>

      <div className="feature-grid">
        <div className="card">
          <h3>Automated analysis</h3>
          <p className="muted" style={{ marginTop: 8 }}>
            Every submission gets a measured centering ratio, corner and edge wear detection, and
            a surface texture pass -- with annotated images showing exactly what was flagged.
          </p>
        </div>
        <div className="card">
          <h3>Multi-company comparison</h3>
          <p className="muted" style={{ marginTop: 8 }}>
            PSA, BGS, CGC, and TAG don&apos;t grade the same way. We highlight the specific points
            of contention that could sway your card&apos;s treatment differently at each company
            -- never a promised numeric grade.
          </p>
        </div>
        <div className="card">
          <h3>Track every submission</h3>
          <p className="muted" style={{ marginTop: 8 }}>
            Create a submission, ship us your card, and watch it move from received to a
            downloadable report -- all from your dashboard.
          </p>
        </div>
      </div>

      <div className="card" style={{ marginTop: 40 }}>
        <h3>An important note</h3>
        <p className="muted" style={{ marginTop: 8 }}>
          ZGrader is an independent estimate, not affiliated with, endorsed by, or a guarantee of
          the outcome from PSA, Beckett Grading Services (BGS), CGC, TAG, or any other
          third-party grading company. Scans are captured on a flatbed scanner, which uses
          diffuse rather than raking light -- surface analysis in particular is lower-confidence
          than what a specialized grading company's photography can catch.
        </p>
      </div>
    </>
  );
}
