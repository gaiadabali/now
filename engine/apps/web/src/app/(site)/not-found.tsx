import Link from 'next/link'

export default function NotFound() {
  return (
    <div className="shell band" style={{ textAlign: 'center', paddingBlock: 'var(--space-3xl)' }}>
      <p className="kicker kicker--red">404</p>
      <h1 className="display display--light" style={{ fontSize: 'var(--t-display)', marginTop: 'var(--space-s)' }}>
        This page has moved on.
      </h1>
      <p className="dek" style={{ margin: 'var(--space-m) auto 0' }}>
        Legacy links are preserved via the permalink map — if you followed one that should work,
        it is worth reporting.
      </p>
      <p style={{ marginTop: 'var(--space-l) '}}>
        <Link className="kicker kicker--red" href="/">Back to the front page →</Link>
      </p>
    </div>
  )
}
