import { NavLink, Outlet, useNavigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import ChatWidget from "./ChatWidget";

const LINKS = [
  ["⌂","Dashboard","/"],["◉","Customers","/customers"],["▣","Products","/products"],
  ["□","Orders","/orders"],["↗","Sales","/sales"],["−","Expenses","/expenses"],
  ["₹","Payments","/payments"],["▤","Invoices","/invoices"],["◫","Reports","/reports"],
];

export default function Layout() {
  const { user, tenant, logout } = useAuth();
  const navigate = useNavigate();
  const initials = user?.full_name ? user.full_name.split(" ").map(n=>n[0]).slice(0,2).join("").toUpperCase() : "?";
  return <div className="app-shell">
    <aside className="sidebar">
      <div className="brand"><div className="brand-mark">S</div><span className="brand-text">{tenant?.business_name || "SMB Manager"}</span></div>
      <div className="nav-section">Workspace</div>
      <nav>{LINKS.map(([icon,label,to])=><NavLink key={to} to={to} end={to==="/"}><span className="nav-icon">{icon}</span><span>{label}</span></NavLink>)}
        {user?.role==="admin" && <NavLink to="/users"><span className="nav-icon">◎</span><span>Users</span></NavLink>}
      </nav>
      <div className="sidebar-footer"><div className="tenant-mini"><strong>{tenant?.business_name || "Your business"}</strong><span>Business workspace</span></div></div>
    </aside>
    <div className="main-area">
      <header className="topbar">
        <div className="searchbox"><span className="search-icon">⌕</span><input placeholder="Search customers, orders, invoices..." disabled title="Use the search box on each page"/></div>
        <div className="top-actions"><button className="icon-btn" title="Notifications">♢</button>
          <div className="user-info"><div className="user-copy"><strong>{user?.full_name}</strong><span className="text-muted">{user?.role}</span></div><div className="avatar">{initials}</div>
          <button className="btn btn-secondary btn-sm" onClick={()=>{logout();navigate("/login")}}>Logout</button></div>
        </div>
      </header>
      <main className="content"><Outlet/></main>
    </div>
    <ChatWidget/>
  </div>;
}
