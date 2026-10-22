import { FormEvent, ReactNode, useEffect, useState } from 'react';
import { currentUser, login, logout, SessionUser, setSignedOutHandler } from '../api';

/**
 * Shows the dashboard only to a signed-in user (the API refuses every route
 * otherwise). Accounts are the web app's: `fraudsim create-user` or DEMO_* env.
 */
export function AuthGate({ children }: { children: (user: SessionUser, signOut: () => void) => ReactNode }) {
  const [user, setUser] = useState<SessionUser | null | undefined>(undefined);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    setSignedOutHandler(() => setUser(null));
    currentUser().then(setUser).catch(() => setUser(null));
  }, []);

  const submit = async (e: FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    const form = new FormData(e.currentTarget);
    setBusy(true);
    setError(null);
    try {
      const failed = await login(String(form.get('email')), String(form.get('password')));
      if (failed) setError(failed);
      else setUser(await currentUser());
    } catch {
      setError('The API is not reachable.');
    } finally {
      setBusy(false);
    }
  };

  const signOut = () => {
    void logout().finally(() => setUser(null));
  };

  if (user === undefined) return <div className="gate"><p className="muted">Checking your session…</p></div>;
  if (user) return <>{children(user, signOut)}</>;
  return (
    <div className="gate">
      <form className="gate-card" onSubmit={submit} aria-labelledby="gate-title">
        <h1 id="gate-title">Sign in</h1>
        <p className="muted">FraudSim live dashboard. Accounts are created by an administrator.</p>
        <label>
          Email
          <input name="email" type="email" autoComplete="username" required />
        </label>
        <label>
          Password
          <input name="password" type="password" autoComplete="current-password" required />
        </label>
        {error && <p className="gate-error" role="alert">{error}</p>}
        <button className="btn primary" type="submit" disabled={busy}>{busy ? 'Signing in…' : 'Sign in'}</button>
      </form>
    </div>
  );
}
