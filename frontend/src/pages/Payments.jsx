import { useEffect, useState } from "react";
import api from "../api/client";
import Modal from "../components/Modal";
import Badge from "../components/Badge";
import { useToast, errorMessage } from "../components/Toast";

const METHODS = ["Cash", "UPI", "Card", "Bank Transfer"];

export default function Payments() {
  const [payments, setPayments] = useState([]);
  const [orders, setOrders] = useState([]);
  const [loading, setLoading] = useState(true);
  const [modalOpen, setModalOpen] = useState(false);
  const [orderId, setOrderId] = useState("");
  const [amount, setAmount] = useState("");
  const [method, setMethod] = useState("Cash");
  const [summary, setSummary] = useState(null);
  const [formError, setFormError] = useState("");
  const toast = useToast();

  async function load() {
    setLoading(true);
    const res = await api.get("/payments");
    setPayments(res.data);
    setLoading(false);
  }

  useEffect(() => { load(); }, []);

  async function openCreate() {
    const res = await api.get("/orders", { params: { payment_status: undefined } });
    // Only show orders that aren't fully paid or cancelled
    setOrders(res.data.filter((o) => o.payment_status !== "Paid" && o.status !== "Cancelled"));
    setOrderId("");
    setAmount("");
    setMethod("Cash");
    setSummary(null);
    setFormError("");
    setModalOpen(true);
  }

  async function handleOrderSelect(id) {
    setOrderId(id);
    setAmount("");
    if (id) {
      const res = await api.get(`/payments/order/${id}/summary`);
      setSummary(res.data);
    } else {
      setSummary(null);
    }
  }

  async function handleSubmit(e) {
    e.preventDefault();
    setFormError("");
    try {
      await api.post("/payments", { order_id: Number(orderId), amount: Number(amount), payment_method: method });
      toast("Payment recorded");
      setModalOpen(false);
      load();
    } catch (err) {
      setFormError(errorMessage(err));
    }
  }

  async function handleDelete(p) {
    if (!confirm("Reverse this payment?")) return;
    try {
      await api.delete(`/payments/${p.id}`);
      toast("Payment reversed");
      load();
    } catch (err) {
      toast(errorMessage(err), "error");
    }
  }

  return (
    <div>
      <div className="page-header">
        <h2>Payments</h2>
        <button className="btn btn-primary" onClick={openCreate}>+ Record Payment</button>
      </div>

      <div className="table-wrap">
        <table>
          <thead>
            <tr><th>ID</th><th>Customer</th><th>Order</th><th>Amount</th><th>Method</th><th>Date</th><th>Status</th><th></th></tr>
          </thead>
          <tbody>
            {loading && <tr><td colSpan={8} className="empty-state">Loading...</td></tr>}
            {!loading && payments.length === 0 && <tr><td colSpan={8} className="empty-state">No payments recorded yet</td></tr>}
            {payments.map((p) => (
              <tr key={p.id}>
                <td>#{p.id}</td>
                <td>{p.customer_name}</td>
                <td>#{p.order_id}</td>
                <td>₹{p.amount}</td>
                <td>{p.payment_method}</td>
                <td>{new Date(p.payment_date).toLocaleDateString()}</td>
                <td><Badge value={p.status} /></td>
                <td><button className="btn btn-danger btn-sm" onClick={() => handleDelete(p)}>Reverse</button></td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {modalOpen && (
        <Modal title="Record Payment" onClose={() => setModalOpen(false)}>
          <form onSubmit={handleSubmit}>
            <div className="form-field full">
              <label>Order</label>
              <select value={orderId} onChange={(e) => handleOrderSelect(e.target.value)} required>
                <option value="">Select an unpaid/partially paid order...</option>
                {orders.map((o) => (
                  <option key={o.id} value={o.id}>
                    #{o.id} — {o.customer_name} — ₹{o.total_amount} ({o.payment_status})
                  </option>
                ))}
              </select>
            </div>

            {summary && (
              <div className="card" style={{ margin: "10px 0", background: "#f9fafb" }}>
                <p style={{ margin: "2px 0" }}>Total order amount: <strong>₹{summary.total_order_amount}</strong></p>
                <p style={{ margin: "2px 0" }}>Amount paid so far: <strong>₹{summary.amount_paid}</strong></p>
                <p style={{ margin: "2px 0" }}>Remaining balance: <strong>₹{summary.remaining_balance}</strong></p>
              </div>
            )}

            <div className="form-grid">
              <div className="form-field">
                <label>Amount (₹)</label>
                <input type="number" step="0.01" min="0.01" max={summary?.remaining_balance || undefined}
                       value={amount} onChange={(e) => setAmount(e.target.value)} required />
              </div>
              <div className="form-field">
                <label>Payment Method</label>
                <select value={method} onChange={(e) => setMethod(e.target.value)}>
                  {METHODS.map((m) => <option key={m} value={m}>{m}</option>)}
                </select>
              </div>
            </div>

            {formError && <div className="form-error">{formError}</div>}
            <div className="modal-actions">
              <button type="button" className="btn btn-secondary" onClick={() => setModalOpen(false)}>Cancel</button>
              <button type="submit" className="btn btn-primary">Record Payment</button>
            </div>
          </form>
        </Modal>
      )}
    </div>
  );
}
