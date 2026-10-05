import { useEffect, useState } from "react";
import api from "../api/client";
import Modal from "../components/Modal";
import { useToast, errorMessage } from "../components/Toast";

const CATEGORIES = ["Rent", "Electricity", "Salary", "Transport", "Purchase", "Maintenance", "Other"];
const METHODS = ["Cash", "UPI", "Card", "Bank Transfer"];

const emptyForm = { category: "Rent", description: "", amount: "", payment_method: "Cash", date: "" };

export default function Expenses() {
  const [expenses, setExpenses] = useState([]);
  const [category, setCategory] = useState("");
  const [dateFrom, setDateFrom] = useState("");
  const [dateTo, setDateTo] = useState("");
  const [loading, setLoading] = useState(true);
  const [modalOpen, setModalOpen] = useState(false);
  const [editing, setEditing] = useState(null);
  const [form, setForm] = useState(emptyForm);
  const [formError, setFormError] = useState("");
  const toast = useToast();

  async function load() {
    setLoading(true);
    const res = await api.get("/expenses", {
      params: {
        category: category || undefined,
        date_from: dateFrom || undefined,
        date_to: dateTo || undefined,
      },
    });
    setExpenses(res.data);
    setLoading(false);
  }

  useEffect(() => { load(); }, [category, dateFrom, dateTo]); // eslint-disable-line

  function openCreate() {
    setEditing(null);
    setForm(emptyForm);
    setFormError("");
    setModalOpen(true);
  }

  function openEdit(e) {
    setEditing(e);
    setForm({
      category: e.category, description: e.description || "", amount: e.amount,
      payment_method: e.payment_method, date: e.date ? e.date.slice(0, 10) : "",
    });
    setFormError("");
    setModalOpen(true);
  }

  async function handleSubmit(e) {
    e.preventDefault();
    setFormError("");
    const payload = { ...form, amount: Number(form.amount) };
    if (!payload.date) delete payload.date;
    try {
      if (editing) {
        await api.put(`/expenses/${editing.id}`, payload);
        toast("Expense updated");
      } else {
        await api.post("/expenses", payload);
        toast("Expense added");
      }
      setModalOpen(false);
      load();
    } catch (err) {
      setFormError(errorMessage(err));
    }
  }

  async function handleDelete(e) {
    if (!confirm("Delete this expense?")) return;
    try {
      await api.delete(`/expenses/${e.id}`);
      toast("Expense deleted");
      load();
    } catch (err) {
      toast(errorMessage(err), "error");
    }
  }

  const total = expenses.reduce((s, e) => s + e.amount, 0);

  return (
    <div>
      <div className="page-header">
        <h2>Expenses</h2>
        <button className="btn btn-primary" onClick={openCreate}>+ Add Expense</button>
      </div>

      <div className="filters-row">
        <select value={category} onChange={(e) => setCategory(e.target.value)}>
          <option value="">All Categories</option>
          {CATEGORIES.map((c) => <option key={c} value={c}>{c}</option>)}
        </select>
        <input type="date" value={dateFrom} onChange={(e) => setDateFrom(e.target.value)} />
        <span className="text-muted">to</span>
        <input type="date" value={dateTo} onChange={(e) => setDateTo(e.target.value)} />
      </div>

      <div className="table-wrap">
        <table>
          <thead>
            <tr><th>ID</th><th>Category</th><th>Description</th><th>Amount</th><th>Date</th><th>Method</th><th></th></tr>
          </thead>
          <tbody>
            {loading && <tr><td colSpan={7} className="empty-state">Loading...</td></tr>}
            {!loading && expenses.length === 0 && <tr><td colSpan={7} className="empty-state">No expenses found</td></tr>}
            {expenses.map((e) => (
              <tr key={e.id}>
                <td>#{e.id}</td>
                <td>{e.category}</td>
                <td>{e.description || "-"}</td>
                <td>₹{e.amount}</td>
                <td>{new Date(e.date).toLocaleDateString()}</td>
                <td>{e.payment_method}</td>
                <td>
                  <button className="btn btn-secondary btn-sm" onClick={() => openEdit(e)}>Edit</button>{" "}
                  <button className="btn btn-danger btn-sm" onClick={() => handleDelete(e)}>Delete</button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {!loading && expenses.length > 0 && (
        <p style={{ textAlign: "right", fontWeight: 700, marginTop: 10 }}>Total: ₹{total.toFixed(2)}</p>
      )}

      {modalOpen && (
        <Modal title={editing ? "Edit Expense" : "Add Expense"} onClose={() => setModalOpen(false)}>
          <form onSubmit={handleSubmit}>
            <div className="form-grid">
              <div className="form-field">
                <label>Category</label>
                <select value={form.category} onChange={(e) => setForm({ ...form, category: e.target.value })}>
                  {CATEGORIES.map((c) => <option key={c} value={c}>{c}</option>)}
                </select>
              </div>
              <div className="form-field">
                <label>Amount (₹)</label>
                <input type="number" step="0.01" min="0.01" value={form.amount} onChange={(e) => setForm({ ...form, amount: e.target.value })} required />
              </div>
              <div className="form-field">
                <label>Payment Method</label>
                <select value={form.payment_method} onChange={(e) => setForm({ ...form, payment_method: e.target.value })}>
                  {METHODS.map((m) => <option key={m} value={m}>{m}</option>)}
                </select>
              </div>
              <div className="form-field">
                <label>Date</label>
                <input type="date" value={form.date} onChange={(e) => setForm({ ...form, date: e.target.value })} />
              </div>
              <div className="form-field full">
                <label>Description</label>
                <textarea rows={2} value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })} />
              </div>
            </div>
            {formError && <div className="form-error">{formError}</div>}
            <div className="modal-actions">
              <button type="button" className="btn btn-secondary" onClick={() => setModalOpen(false)}>Cancel</button>
              <button type="submit" className="btn btn-primary">{editing ? "Save Changes" : "Add Expense"}</button>
            </div>
          </form>
        </Modal>
      )}
    </div>
  );
}
