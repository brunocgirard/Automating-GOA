"use client";

import Link from "next/link";
import { FormEvent, useEffect, useState } from "react";
import { useRouter } from "next/navigation";

import { fetchCurrentUser, register } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";

export default function RegisterPage() {
  const router = useRouter();
  const [nextPath, setNextPath] = useState("/");

  const [username, setUsername] = useState("");
  const [displayName, setDisplayName] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
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

    const trimmedUsername = username.trim();
    const trimmedDisplayName = displayName.trim();
    if (!trimmedUsername) {
      setError("Username is required.");
      setSubmitting(false);
      return;
    }
    if (password.length < 8) {
      setError("Password must be at least 8 characters.");
      setSubmitting(false);
      return;
    }
    if (password !== confirmPassword) {
      setError("Passwords do not match.");
      setSubmitting(false);
      return;
    }

    try {
      await register({
        username: trimmedUsername,
        display_name: trimmedDisplayName || null,
        password,
      });
      router.replace(nextPath);
    } catch (submitError) {
      setError(submitError instanceof Error ? submitError.message : "Registration failed.");
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
          <h1 className="text-xl font-semibold text-neutral-900">Create Account</h1>
          <p className="mt-1 text-sm text-neutral-600">Register your PM tool account.</p>
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
            autoComplete="name"
            placeholder="Display name (optional)"
            value={displayName}
            onChange={(event) => setDisplayName(event.target.value)}
            disabled={submitting}
          />
          <Input
            type="password"
            autoComplete="new-password"
            placeholder="Password (min 8 chars)"
            value={password}
            onChange={(event) => setPassword(event.target.value)}
            disabled={submitting}
          />
          <Input
            type="password"
            autoComplete="new-password"
            placeholder="Confirm password"
            value={confirmPassword}
            onChange={(event) => setConfirmPassword(event.target.value)}
            disabled={submitting}
          />
        </div>

        {error ? <p className="mt-3 text-sm text-red-700">{error}</p> : null}

        <Button
          className="mt-4 w-full"
          type="submit"
          disabled={submitting || !username || !password || !confirmPassword}
        >
          {submitting ? "Creating account..." : "Create Account"}
        </Button>

        <p className="mt-4 text-center text-sm text-neutral-600">
          Already have an account?{" "}
          <Link href={`/login?next=${encodeURIComponent(nextPath)}`} className="font-medium text-neutral-900 underline">
            Sign in
          </Link>
        </p>
      </form>
    </div>
  );
}
