import { useEffect, useState } from "react";
import api from "../api/client";
import Modal from "../components/Modal";
import Badge from "../components/Badge";
import { useToast, errorMessage } from "../components/Toast";

const ORDER_STATUSES = ["Pending", "Confirmed", "Processing", "Shipped", "Delivered", "Cancelled"];

export default function Orders() {
  const [orders, setOrders] = useState([]);
  const [customers, setCustomers] = useState([]);
  const [products, setProducts] = useState([]);
  const [statusFilter, setStatusFilter] = useState("");
  const [loading, setLoading] = useState(true);
  const [modalOpen, setModalOpen] = useState(false);
  const [formError, setFormError] = useState("");
  const [customerId, setCustomerId] = useState("");
  const [items, setItems] = useState([{ product_id: "", quantity: 1 }]);
  const [detail, setDetail] = useState(null);
  const toast = useToast();

  async function load() {
    setLoading(true);
    const res = await api.get("/orders", { params: statusFilter ? { status: statusFilter } : {} });
    setOrders(res.data);
    setLoading(false);
  }

  useEffect(() => { load(); }, [statusFilter]); // eslint-disable-line

  async function openCreate() {
    const [c, p] = await Promise.all([api.get("/customers"), api.get("/products")]);
    setCustomers(c.data);
    setProducts(p.data);
    setCustomerId("");
    setItems([{ product_id: "", quantity: 1 }]);
    setFormError("");
    setModalOpen(true);
  }

  function updateItem(idx, field, value) {
    const next = [...items];
    next[idx] = { ...next[idx], [field]: value };
    setItems(next);
  }

  async function handleSubmit(e) {
    e.preventDefault();
    setFormError("");
    try {
      await api.post("/orders", {
        customer_id: Number(customerId),
        items: items.filter((i) => i.product_id).map((i) => ({ product_id: Number(i.product_id), quantity: Number(i.quantity) })),
      });
      toast("Order created");
      setModalOpen(false);
      load();
    } catch (err) {
      setFormError(errorMessage(err));
    }
  }

  async function updateStatus(order, status) {
    try {
      await api.patch(`/orders/${order.id}/status`, { status });
      toast(`Order #${order.id} marked as ${status}`);
      load();
    } catch (err) {
      toast(errorMessage(err), "error");
    }
  }

  const estimatedTotal = items.reduce((sum, i) => {
    const p = products.find((pr) => pr.id === Number(i.product_id));
    return sum + (p ? p.price * Number(i.quantity || 0) : 0);
  }, 0);

  return (
    <div>
      <div className="page-header">
        <h2>Orders</h2>
        <button className="btn btn-primary" onClick={openCreate}>+ New Order</button>
      </div>

      <div className="filters-row">
        <select value={statusFilter} onChange={(e) => setStatusFilter(e.target.value)}>
          <option value="">All Statuses</option>
          {ORDER_STATUSES.map((s) => <option key={s} value={s}>{s}</option>)}
        </select>
      </div>

      <div className="table-wrap">
        <table>
          <thead>
            <tr><th>Order</th><th>Customer</th><th>Total</th><th>Date</th><th>Status</th><th>Payment</th><th></th></tr>
          </thead>
          <tbody>
            {loading && <tr><td colSpan={7} className="empty-state">Loading...</td></tr>}
            {!loading && orders.length === 0 && <tr><td colSpan={7} className="empty-state">No orders found</td></tr>}
            {orders.map((o) => (
              <tr key={o.id}>
                <td><a onClick={() => setDetail(o)} style={{ cursor: "pointer", color: "#4f46e5", fontWeight: 600 }}>#{o.id}</a></td>
                <td>{o.customer_name}</td>
                <td>₹{o.total_amount}</td>
                <td>{new Date(o.order_date).toLocaleDateString()}</td>
                <td><Badge value={o.status} /></td>
                <td><Badge value={o.payment_status} /></td>
                <td>
                  <select value={o.status} onChange={(e) => updateStatus(o, e.target.value)} disabled={o.status === "Cancelled"}>
                    {ORDER_STATUSES.map((s) => <option key={s} value={s}>{s}</option>)}
                  </select>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {modalOpen && (
        <Modal title="New Order" onClose={() => setModalOpen(false)}>
          <form onSubmit={handleSubmit}>
            <div className="form-field full">
              <label>Customer</label>
              <select value={customerId} onChange={(e) => setCustomerId(e.target.value)} required>
                <option value="">Select customer...</option>
                {customers.map((c) => <option key={c.id} value={c.id}>{c.name} ({c.phone})</option>)}
              </select>
            </div>

            <label style={{ fontSize: "0.8rem", fontWeight: 600, color: "#6b7280" }}>Items</label>
            {items.map((item, idx) => (
              <div key={idx} className="form-grid" style={{ marginTop: 6 }}>
                <div className="form-field">
                  <select value={item.product_id} onChange={(e) => updateItem(idx, "product_id", e.target.value)} required>
                    <option value="">Select product...</option>
                    {products.map((p) => (
                      <option key={p.id} value={p.id} disabled={p.quantity === 0}>
                        {p.name} — ₹{p.price} ({p.quantity} in stock)
                      </option>
                    ))}
                  </select>
                </div>
                <div className="form-field" style={{ flexDirection: "row", alignItems: "center", gap: 8 }}>
                  <input type="number" min="1" style={{ width: 90 }} value={item.quantity}
                         onChange={(e) => updateItem(idx, "quantity", e.target.value)} required />
                  {items.length > 1 && (
                    <button type="button" className="btn btn-danger btn-sm" onClick={() => setItems(items.filter((_, i) => i !== idx))}>✕</button>
                  )}
                </div>
              </div>
            ))}
            <button type="button" className="btn btn-secondary btn-sm" style={{ marginTop: 8 }}
                    onClick={() => setItems([...items, { product_id: "", quantity: 1 }])}>
              + Add another product
            </button>

            <p style={{ marginTop: 14, fontWeight: 700 }}>Estimated Total: ₹{estimatedTotal.toFixed(2)}</p>

            {formError && <div className="form-error">{formError}</div>}
            <div className="modal-actions">
              <button type="button" className="btn btn-secondary" onClick={() => setModalOpen(false)}>Cancel</button>
              <button type="submit" className="btn btn-primary">Create Order</button>
            </div>
          </form>
        </Modal>
      )}

      {detail && (
        <Modal title={`Order #${detail.id}`} onClose={() => setDetail(null)}>
          <p><strong>Customer:</strong> {detail.customer_name}</p>
          <p><strong>Status:</strong> <Badge value={detail.status} /> &nbsp; <strong>Payment:</strong> <Badge value={detail.payment_status} /></p>
          <div className="table-wrap">
            <table>
              <thead><tr><th>Product</th><th>Qty</th><th>Unit Price</th><th>Line Total</th></tr></thead>
              <tbody>
                {detail.items.map((i) => (
                  <tr key={i.id}><td>{i.product_name}</td><td>{i.quantity}</td><td>₹{i.unit_price}</td><td>₹{i.line_total}</td></tr>
                ))}
              </tbody>
            </table>
          </div>
          <p style={{ textAlign: "right", fontWeight: 700, marginTop: 10 }}>Total: ₹{detail.total_amount}</p>
          <div className="modal-actions">
            <button className="btn btn-secondary" onClick={() => setDetail(null)}>Close</button>
          </div>
        </Modal>
      )}
    </div>
  );
}
