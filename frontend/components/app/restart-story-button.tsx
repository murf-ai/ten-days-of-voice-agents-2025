"use client";

import React, { useState } from "react";

export function RestartStoryButton() {
  const [loading, setLoading] = useState(false);
  const [opening, setOpening] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function handleRestart() {
    setLoading(true);
    setError(null);
    setOpening(null);
    try {
      const res = await fetch("http://127.0.0.1:8765/restart", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ universe: "fantasy" }),
      });
      if (!res.ok) {
        const txt = await res.text();
        throw new Error(txt || `Status ${res.status}`);
      }
      const data = await res.json();
      setOpening(data.opening || "(no opening returned)");
    } catch (e: any) {
      setError(e?.message || String(e));
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="mb-3 flex w-full items-center justify-center gap-3">
      <button
        className="rounded-md bg-emerald-600 px-3 py-2 text-sm font-medium text-white hover:bg-emerald-500 disabled:opacity-60"
        onClick={handleRestart}
        disabled={loading}
      >
        {loading ? "Restarting…" : "Restart Story"}
      </button>

      {opening && (
        <div className="max-w-xl truncate rounded bg-muted px-3 py-2 text-sm text-foreground">
          {opening}
        </div>
      )}

      {error && <div className="text-sm text-red-500">Error: {error}</div>}
    </div>
  );
}
