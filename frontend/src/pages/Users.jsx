import { useEffect, useState } from "react";
import api from "../api/client";
import Modal from "../components/Modal";
import Badge from "../components/Badge";
import { useAuth } from "../context/AuthContext";
import { useToast, errorMessage } from "../components/Toast";

const emptyForm = { full_name: "", email: "", password: "", role: "staff" };

export default function Users() {
  const [users, setUsers] = useState([]);
  const [loading, setLoading] = useState(true);
  const [modalOpen, setModalOpen] = useState(false);
  const [form, setForm] = useState(emptyForm);
  const [formError, setFormError] = useState("");
  const { tenant } = useAuth();
  const toast = useToast();

  async function load() {
    setLoading(true);
    try {
      const res = await api.get("/auth/users");
      setUsers(res.data);
    } catch (err) {
      toast(errorMessage(err), "error");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { load(); }, []);

  function openCreate() {
    setForm(emptyForm);
    setFormError("");
    setModalOpen(true);
  }

  async function handleSubmit(e) {
    e.preventDefault();
    setFormError("");
    try {
      await api.post("/auth/staff", form);
      toast("User added");
      setModalOpen(false);
      load();
    } catch (err) {
      setFormError(errorMessage(err));
    }
  }

  async function deactivate(u) {
    if (!confirm(`Deactivate ${u.full_name}?`)) return;
    try {
      await api.patch(`/auth/users/${u.id}/deactivate`);
      toast("User deactivated");
      load();
    } catch (err) {
      toast(errorMessage(err), "error");
    }
  }

  return (
    <div>
      <div className="page-header">
        <h2>Users</h2>
        <button className="btn btn-primary" onClick={openCreate}>+ Add User</button>
      </div>
      <p className="text-muted" style={{ marginTop: -10 }}>
        Admin only. Accounts created here belong to <strong>{tenant?.business_name}</strong> and can't see other businesses' data.
      </p>

      <div className="table-wrap">
        <table>
          <thead><tr><th>ID</th><th>Name</th><th>Email</th><th>Role</th><th>Status</th><th></th></tr></thead>
          <tbody>
            {loading && <tr><td colSpan={6} className="empty-state">Loading...</td></tr>}
            {!loading && users.map((u) => (
              <tr key={u.id}>
                <td>#{u.id}</td>
                <td>{u.full_name}</td>
                <td>{u.email}</td>
                <td><Badge value={u.role} /></td>
                <td>{u.is_active ? "Active" : "Deactivated"}</td>
                <td>
                  {u.is_active && (
                    <button className="btn btn-danger btn-sm" onClick={() => deactivate(u)}>Deactivate</button>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {modalOpen && (
        <Modal title="Add User" onClose={() => setModalOpen(false)}>
          <form onSubmit={handleSubmit}>
            <div className="form-grid">
              <div className="form-field full">
                <label>Full name</label>
                <input value={form.full_name} onChange={(e) => setForm({ ...form, full_name: e.target.value })} required />
              </div>
              <div className="form-field full">
                <label>Email</label>
                <input type="email" value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} required />
              </div>
              <div className="form-field">
                <label>Password</label>
                <input type="password" minLength={8} value={form.password} onChange={(e) => setForm({ ...form, password: e.target.value })} required />
              </div>
              <div className="form-field">
                <label>Role</label>
                <select value={form.role} onChange={(e) => setForm({ ...form, role: e.target.value })}>
                  <option value="staff">Staff</option>
                  <option value="admin">Admin</option>
                </select>
              </div>
            </div>
            {formError && <div className="form-error">{formError}</div>}
            <div className="modal-actions">
              <button type="button" className="btn btn-secondary" onClick={() => setModalOpen(false)}>Cancel</button>
              <button type="submit" className="btn btn-primary">Add User</button>
            </div>
          </form>
        </Modal>
      )}
    </div>
  );
}
