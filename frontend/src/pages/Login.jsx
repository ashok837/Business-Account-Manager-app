import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import { errorMessage } from "../components/Toast";

export default function Login() {
 const {login}=useAuth(), navigate=useNavigate(); const [email,setEmail]=useState("admin@business.com"),[password,setPassword]=useState(""),[error,setError]=useState(""),[loading,setLoading]=useState(false);
 async function handleSubmit(e){e.preventDefault();setError("");setLoading(true);try{await login(email,password);navigate("/")}catch(err){setError(errorMessage(err))}finally{setLoading(false)}}
 return <div className="auth-wrap">
  <section className="auth-visual"><div className="auth-brand">◈ SMB Manager</div><h2>Run your business from one intelligent workspace.</h2><p>Customers, products, sales, payments and reporting — organized in one clean command center.</p>
   <img className="auth-hero-img" src="/images/auth-hero.svg" alt="Business dashboard preview"/><div className="auth-features"><div className="auth-feature">✓ Real-time business visibility</div><div className="auth-feature">✓ Secure multi-tenant workspace</div><div className="auth-feature">✓ Faster billing & collections</div></div>
  </section>
  <section className="auth-card-wrap"><form className="auth-card" onSubmit={handleSubmit}><div className="eyebrow">Welcome back</div><h1>Sign in to your workspace</h1><p className="subtitle">Enter your credentials to continue.</p>
   <div className="form-field"><label>Email address</label><input type="email" value={email} onChange={e=>setEmail(e.target.value)} required placeholder="you@business.com"/></div>
   <div className="form-field" style={{marginTop:16}}><label>Password</label><input type="password" value={password} onChange={e=>setPassword(e.target.value)} required placeholder="Enter your password"/></div>
   {error&&<div className="form-error">{error}</div>}<button className="btn btn-primary" type="submit" disabled={loading}>{loading?"Signing in…":"Sign In →"}</button>
   <div className="auth-switch">New business? <Link to="/register">Create your workspace</Link></div><div className="auth-note">Demo account: admin@business.com / admin12345<br/>Available after running seed.py</div>
  </form></section>
 </div>;
}
