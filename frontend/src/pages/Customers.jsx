import { useEffect, useState } from "react";
import api from "../api/client";
import Modal from "../components/Modal";
import Badge from "../components/Badge";
import { useToast, errorMessage } from "../components/Toast";

const emptyForm = { name: "", phone: "", email: "", address: "" };

export default function Customers() {
  const [customers, setCustomers] = useState([]);
  const [search, setSearch] = useState("");
  const [loading, setLoading] = useState(true);
  const [modalOpen, setModalOpen] = useState(false);
  const [editing, setEditing] = useState(null);
  const [form, setForm] = useState(emptyForm);
  const [formError, setFormError] = useState("");
  const [detailCustomer, setDetailCustomer] = useState(null);
  const [detailOrders, setDetailOrders] = useState([]);
  const [detailPayments, setDetailPayments] = useState([]);
  const toast = useToast();

  async function load() {
    setLoading(true);
    const res = await api.get("/customers", { params: search ? { search } : {} });
    setCustomers(res.data);
    setLoading(false);
  }

  useEffect(() => { load(); }, []); // eslint-disable-line

  function openCreate() {
    setEditing(null);
    setForm(emptyForm);
    setFormError("");
    setModalOpen(true);
  }

  function openEdit(c) {
    setEditing(c);
    setForm({ name: c.name, phone: c.phone, email: c.email || "", address: c.address || "" });
    setFormError("");
    setModalOpen(true);
  }

  async function handleSubmit(e) {
    e.preventDefault();
    setFormError("");
    try {
      if (editing) {
        await api.put(`/customers/${editing.id}`, form);
        toast("Customer updated");
      } else {
        await api.post("/customers", form);
        toast("Customer added");
      }
      setModalOpen(false);
      load();
    } catch (err) {
      setFormError(errorMessage(err));
    }
  }

  async function handleDelete(c) {
    if (!confirm(`Delete customer "${c.name}"?`)) return;
    try {
      await api.delete(`/customers/${c.id}`);
      toast("Customer deleted");
      load();
    } catch (err) {
      toast(errorMessage(err), "error");
    }
  }

  async function openDetail(c) {
    setDetailCustomer(c);
    const [orders, payments] = await Promise.all([
      api.get(`/customers/${c.id}/orders`),
      api.get(`/customers/${c.id}/payments`),
    ]);
    setDetailOrders(orders.data);
    setDetailPayments(payments.data);
  }

  return (
    <div>
      <div className="page-header">
        <h2>Customers</h2>
        <button className="btn btn-primary" onClick={openCreate}>+ Add Customer</button>
      </div>

      <div className="filters-row">
        <input
          placeholder="Search by name, phone, or email..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && load()}
        />
        <button className="btn btn-secondary btn-sm" onClick={load}>Search</button>
      </div>

      <div className="table-wrap">
        <table>
          <thead>
            <tr><th>ID</th><th>Name</th><th>Phone</th><th>Email</th><th>Address</th><th>Created</th><th></th></tr>
          </thead>
          <tbody>
            {loading && <tr><td colSpan={7} className="empty-state">Loading...</td></tr>}
            {!loading && customers.length === 0 && <tr><td colSpan={7} className="empty-state">No customers found</td></tr>}
            {customers.map((c) => (
              <tr key={c.id}>
                <td>#{c.id}</td>
                <td><a onClick={() => openDetail(c)} style={{ cursor: "pointer", color: "#4f46e5", fontWeight: 600 }}>{c.name}</a></td>
                <td>{c.phone}</td>
                <td>{c.email || "-"}</td>
                <td>{c.address || "-"}</td>
                <td>{new Date(c.created_at).toLocaleDateString()}</td>
                <td>
                  <button className="btn btn-secondary btn-sm" onClick={() => openEdit(c)}>Edit</button>{" "}
                  <button className="btn btn-danger btn-sm" onClick={() => handleDelete(c)}>Delete</button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {modalOpen && (
        <Modal title={editing ? "Edit Customer" : "Add Customer"} onClose={() => setModalOpen(false)}>
          <form onSubmit={handleSubmit}>
            <div className="form-grid">
              <div className="form-field full">
                <label>Name</label>
                <input value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} required />
              </div>
              <div className="form-field">
                <label>Phone</label>
                <input value={form.phone} onChange={(e) => setForm({ ...form, phone: e.target.value })} required />
              </div>
              <div className="form-field">
                <label>Email</label>
                <input type="email" value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} />
              </div>
              <div className="form-field full">
                <label>Address</label>
                <textarea rows={2} value={form.address} onChange={(e) => setForm({ ...form, address: e.target.value })} />
              </div>
            </div>
            {formError && <div className="form-error">{formError}</div>}
            <div className="modal-actions">
              <button type="button" className="btn btn-secondary" onClick={() => setModalOpen(false)}>Cancel</button>
              <button type="submit" className="btn btn-primary">{editing ? "Save Changes" : "Add Customer"}</button>
            </div>
          </form>
        </Modal>
      )}

      {detailCustomer && (
        <Modal title={`${detailCustomer.name} — Details`} onClose={() => setDetailCustomer(null)}>
          <p className="text-muted">{detailCustomer.phone} · {detailCustomer.email || "no email"}</p>

          <h4>Order History</h4>
          <div className="table-wrap" style={{ marginBottom: 16 }}>
            <table>
              <thead><tr><th>Order</th><th>Total</th><th>Status</th></tr></thead>
              <tbody>
                {detailOrders.length === 0 && <tr><td colSpan={3} className="empty-state">No orders</td></tr>}
                {detailOrders.map((o) => (
                  <tr key={o.id}><td>#{o.id}</td><td>₹{o.total_amount}</td><td><Badge value={o.status} /></td></tr>
                ))}
              </tbody>
            </table>
          </div>

          <h4>Payment History</h4>
          <div className="table-wrap">
            <table>
              <thead><tr><th>Payment</th><th>Amount</th><th>Method</th></tr></thead>
              <tbody>
                {detailPayments.length === 0 && <tr><td colSpan={3} className="empty-state">No payments</td></tr>}
                {detailPayments.map((p) => (
                  <tr key={p.id}><td>#{p.id}</td><td>₹{p.amount}</td><td>{p.payment_method}</td></tr>
                ))}
              </tbody>
            </table>
          </div>
          <div className="modal-actions">
            <button className="btn btn-secondary" onClick={() => setDetailCustomer(null)}>Close</button>
          </div>
        </Modal>
      )}
    </div>
  );
}
