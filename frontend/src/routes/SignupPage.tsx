import { FormEvent, useState, startTransition } from "react";
import { Link, useNavigate } from "react-router-dom";

import { signup } from "../api/auth";
import { getErrorMessage } from "../lib/api/errors";

export function SignupPage() {
  const navigate = useNavigate();
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setIsSubmitting(true);
    setErrorMessage(null);

    const formData = new FormData(event.currentTarget);

    try {
      await signup({
        display_name: String(formData.get("displayName") ?? ""),
        email: String(formData.get("email") ?? ""),
        password: String(formData.get("password") ?? ""),
      });
      startTransition(() => {
        navigate("/trips");
      });
    } catch (error) {
      setErrorMessage(getErrorMessage(error, "Sign-up failed."));
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <section className="auth-layout">
      <article className="status-card auth-card">
        <p className="status-label">Account foundation</p>
        <h2>Create your planner account</h2>
        <p className="lede">
          This first pass keeps auth intentionally small-business sized: email, password, and a
          durable session cookie.
        </p>
        <form className="auth-form" onSubmit={handleSubmit}>
          <label>
            Display name
            <input name="displayName" type="text" autoComplete="name" required />
          </label>
          <label>
            Email
            <input name="email" type="email" autoComplete="email" required />
          </label>
          <label>
            Password
            <input name="password" type="password" autoComplete="new-password" minLength={8} required />
          </label>
          {errorMessage ? (
            <p className="auth-error" role="alert">
              {errorMessage}
            </p>
          ) : null}
          <button type="submit" disabled={isSubmitting}>
            {isSubmitting ? "Creating account..." : "Create account"}
          </button>
        </form>
        <p className="auth-switch">
          Already have an account? <Link to="/login">Sign in</Link>
        </p>
      </article>
    </section>
  );
}
