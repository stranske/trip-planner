import { FormEvent, useState, startTransition } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";

import { login } from "../api/auth";
import { getErrorMessage } from "../lib/api/errors";

function resolveNextPath(searchParams: URLSearchParams): string {
  const next = searchParams.get("next");
  if (!next || !next.startsWith("/")) {
    return "/trips";
  }
  return next;
}

export function LoginPage() {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setIsSubmitting(true);
    setErrorMessage(null);

    const formData = new FormData(event.currentTarget);

    try {
      await login({
        email: String(formData.get("email") ?? ""),
        password: String(formData.get("password") ?? ""),
      });
      const nextPath = resolveNextPath(searchParams);
      startTransition(() => {
        navigate(nextPath);
      });
    } catch (error) {
      setErrorMessage(getErrorMessage(error, "Sign-in failed."));
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <section className="auth-layout">
      <article className="status-card auth-card">
        <p className="status-label">Welcome back</p>
        <h2>Sign in to resume planning</h2>
        <p className="lede">
          Continue working with your saved trips, route comparisons, notes, and planning history.
        </p>
        <form className="auth-form" onSubmit={handleSubmit}>
          <label>
            Email
            <input name="email" type="email" autoComplete="email" required />
          </label>
          <label>
            Password
            <input name="password" type="password" autoComplete="current-password" required />
          </label>
          {errorMessage ? (
            <p className="auth-error" role="alert">
              {errorMessage}
            </p>
          ) : null}
          <button type="submit" disabled={isSubmitting}>
            {isSubmitting ? "Signing in..." : "Sign in"}
          </button>
        </form>
        <p className="auth-switch">
          New here? <Link to="/signup">Create an account</Link>
        </p>
      </article>
    </section>
  );
}
