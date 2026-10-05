import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import { errorMessage } from "../components/Toast";

export default function Register() {
  const { registerBusiness } = useAuth();
  const navigate = useNavigate();
  const [businessName, setBusinessName] = useState("");
  const [fullName, setFullName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  async function handleSubmit(e) {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      await registerBusiness(businessName, fullName, email, password);
      navigate("/");
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="auth-wrap">
      <section className="auth-visual">
        <div className="auth-brand">◈ SMB Manager</div>
        <h2>Start managing your business in minutes.</h2>
        <p>Create a private workspace for your customers, products, orders and payments.</p>
        <img className="auth-hero-img" src="/images/auth-hero.svg" alt="Business dashboard preview" />
      </section>
      <section className="auth-card-wrap">
      <form className="auth-card" onSubmit={handleSubmit}>
        <h1>Set up your business</h1>
        <p className="subtitle">
          This creates your own private workspace. You'll be the Admin, and can
          add staff accounts afterwards from the Users page.
        </p>

        <div className="form-field">
          <label>Business name</label>
          <input value={businessName} onChange={(e) => setBusinessName(e.target.value)} required />
        </div>
        <div className="form-field">
          <label>Your full name</label>
          <input value={fullName} onChange={(e) => setFullName(e.target.value)} required />
        </div>
        <div className="form-field">
          <label>Email</label>
          <input type="email" value={email} onChange={(e) => setEmail(e.target.value)} required />
        </div>
        <div className="form-field">
          <label>Password</label>
          <input type="password" minLength={8} value={password} onChange={(e) => setPassword(e.target.value)} required />
          <span className="text-muted" style={{ fontSize: "0.76rem" }}>At least 8 characters, with a letter and a number.</span>
        </div>

        {error && <div className="form-error">{error}</div>}

        <button className="btn btn-primary" type="submit" disabled={loading}>
          {loading ? "Creating..." : "Create Business Account"}
        </button>

        <div className="auth-switch">
          Already have an account? <Link to="/login">Sign in</Link>
        </div>
      </form>
      </section>
    </div>
  );
}
