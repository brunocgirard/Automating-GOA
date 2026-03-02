"use client";

import Link from "next/link";
import { FormEvent, useEffect, useState } from "react";
import { useRouter } from "next/navigation";

import { fetchCurrentUser, login } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";

export default function LoginPage() {
  const router = useRouter();
  const [nextPath, setNextPath] = useState("/");

  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (typeof window !== "undefined") {
      const raw = new URLSearchParams(window.location.search).get("next");
      if (raw && raw.startsWith("/")) {
        setNextPath(raw);
      }
    }

    let active = true;
    void fetchCurrentUser()
      .then(() => {
        if (!active) return;
        router.replace(nextPath);
      })
      .catch(() => {
        // Expected when not authenticated.
      });

    return () => {
      active = false;
    };
  }, [nextPath, router]);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSubmitting(true);
    setError(null);

    try {
      await login({ username, password });
      router.replace(nextPath);
    } catch (submitError) {
      setError(submitError instanceof Error ? submitError.message : "Login failed.");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-neutral-100 px-4">
      <form
        onSubmit={handleSubmit}
        className="w-full max-w-sm rounded-xl border border-neutral-200 bg-white p-6 shadow-sm"
      >
        <div className="mb-5">
          <h1 className="text-xl font-semibold text-neutral-900">Sign In</h1>
          <p className="mt-1 text-sm text-neutral-600">Use your PM tool account credentials.</p>
        </div>

        <div className="space-y-3">
          <Input
            autoComplete="username"
            placeholder="Username"
            value={username}
            onChange={(event) => setUsername(event.target.value)}
            disabled={submitting}
          />
          <Input
            type="password"
            autoComplete="current-password"
            placeholder="Password"
            value={password}
            onChange={(event) => setPassword(event.target.value)}
            disabled={submitting}
          />
        </div>

        {error ? <p className="mt-3 text-sm text-red-700">{error}</p> : null}

        <Button className="mt-4 w-full" type="submit" disabled={submitting || !username || !password}>
          {submitting ? "Signing in..." : "Sign In"}
        </Button>

        <p className="mt-4 text-center text-sm text-neutral-600">
          Need an account?{" "}
          <Link
            href={`/register?next=${encodeURIComponent(nextPath)}`}
            className="font-medium text-neutral-900 underline"
          >
            Create one
          </Link>
        </p>
      </form>
    </div>
  );
}
