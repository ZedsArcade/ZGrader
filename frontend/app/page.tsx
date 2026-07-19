import Link from "next/link";
import { Card, buttonVariants } from "@heroui/react";

export default function HomePage() {
  return (
    <>
      <section className="flex flex-col items-start gap-5 py-10">
        <h1 className="text-4xl font-bold tracking-tight text-foreground sm:text-5xl">
          Know before you submit.
        </h1>
        <p className="max-w-2xl text-lg text-muted">
          ZGrader is an independent pre-grading service for trading card games. Send us your
          cards, and we&apos;ll scan and analyze centering, corners, edges, and surface, then show
          you exactly how PSA, BGS, CGC, and TAG are likely to treat each one before you pay to
          submit for real.
        </p>
        <div className="flex flex-wrap gap-3">
          <Link href="/register" className={buttonVariants({ variant: "primary" })}>
            Get started
          </Link>
          <Link href="/login" className={buttonVariants({ variant: "outline" })}>
            Log in
          </Link>
        </div>
      </section>

      <div className="grid gap-5 py-6 sm:grid-cols-2 lg:grid-cols-3">
        <Card>
          <Card.Header>
            <Card.Title>Automated analysis</Card.Title>
          </Card.Header>
          <Card.Content>
            <p className="text-sm text-muted">
              Every submission gets a measured centering ratio, corner and edge wear detection,
              and a surface texture pass -- with annotated images showing exactly what was
              flagged.
            </p>
          </Card.Content>
        </Card>
        <Card>
          <Card.Header>
            <Card.Title>Multi-company comparison</Card.Title>
          </Card.Header>
          <Card.Content>
            <p className="text-sm text-muted">
              PSA, BGS, CGC, and TAG don&apos;t grade the same way. We highlight the specific
              points of contention that could sway your card&apos;s treatment differently at each
              company -- never a promised numeric grade.
            </p>
          </Card.Content>
        </Card>
        <Card>
          <Card.Header>
            <Card.Title>Track every submission</Card.Title>
          </Card.Header>
          <Card.Content>
            <p className="text-sm text-muted">
              Create a submission, ship us your card, and watch it move from received to a
              downloadable report -- all from your dashboard.
            </p>
          </Card.Content>
        </Card>
      </div>

      <Card className="mt-4">
        <Card.Header>
          <Card.Title>An important note</Card.Title>
        </Card.Header>
        <Card.Content>
          <p className="text-sm text-muted">
            ZGrader is an independent estimate, not affiliated with, endorsed by, or a guarantee
            of the outcome from PSA, Beckett Grading Services (BGS), CGC, TAG, or any other
            third-party grading company. Scans are captured on a flatbed scanner, which uses
            diffuse rather than raking light -- surface analysis in particular is lower-confidence
            than what a specialized grading company&apos;s photography can catch.
          </p>
        </Card.Content>
      </Card>
    </>
  );
}
