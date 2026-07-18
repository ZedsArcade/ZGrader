"use client";

import { useEffect, useState, type FormEvent } from "react";
import { useRouter } from "next/navigation";
import RequireAuth from "@/components/RequireAuth";
import { useAuth } from "@/lib/auth-context";
import * as api from "@/lib/api";

function NewSubmissionForm() {
  const { token } = useAuth();
  const router = useRouter();
  const [games, setGames] = useState<api.Game[]>([]);
  const [game, setGame] = useState("");
  const [cardName, setCardName] = useState("");
  const [setName, setSetName] = useState("");
  const [cardNumber, setCardNumber] = useState("");
  const [foil, setFoil] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    api.getGames().then((list) => {
      setGames(list);
      if (list.length > 0) setGame(list[0].game);
    });
  }, []);

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    if (!token) return;
    setError(null);
    setSubmitting(true);
    try {
      const submission = await api.createSubmission(token, {
        game,
        card_name: cardName,
        set_name: setName || undefined,
        card_number: cardNumber || undefined,
        foil,
      });
      router.push(`/dashboard/${submission.submission_code}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to create submission");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="card" style={{ maxWidth: 520 }}>
      <div className="page-header">
        <h1>New submission</h1>
        <p>Tell us about the card, then ship it to us for scanning.</p>
      </div>
      {error && <div className="alert alert-error">{error}</div>}
      <form className="stack" onSubmit={handleSubmit}>
        <div>
          <label htmlFor="game">Game</label>
          <select id="game" value={game} onChange={(e) => setGame(e.target.value)} required>
            {games.map((g) => (
              <option key={g.game} value={g.game}>
                {g.game}
                {!g.verified ? " (dimensions unverified)" : ""}
              </option>
            ))}
          </select>
        </div>
        <div>
          <label htmlFor="card-name">Card name</label>
          <input
            id="card-name"
            type="text"
            required
            value={cardName}
            onChange={(e) => setCardName(e.target.value)}
          />
        </div>
        <div>
          <label htmlFor="set-name">Set (optional)</label>
          <input id="set-name" type="text" value={setName} onChange={(e) => setSetName(e.target.value)} />
        </div>
        <div>
          <label htmlFor="card-number">Card number (optional)</label>
          <input
            id="card-number"
            type="text"
            value={cardNumber}
            onChange={(e) => setCardNumber(e.target.value)}
          />
        </div>
        <div className="checkbox-row">
          <input id="foil" type="checkbox" checked={foil} onChange={(e) => setFoil(e.target.checked)} />
          <label htmlFor="foil" style={{ margin: 0 }}>
            Foil / holo
          </label>
        </div>
        <button className="btn" type="submit" disabled={submitting || !game}>
          {submitting ? "Creating…" : "Create submission"}
        </button>
      </form>
    </div>
  );
}

export default function NewSubmissionPage() {
  return (
    <RequireAuth>
      <NewSubmissionForm />
    </RequireAuth>
  );
}
