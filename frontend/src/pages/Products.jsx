import { useEffect, useState } from "react";
import api from "../api/client";
import Modal from "../components/Modal";
import ProductThumb from "../components/ProductThumb";
import EmptyState from "../components/EmptyState";
import { useToast, errorMessage } from "../components/Toast";

const emptyForm = { name: "", category: "", price: "", quantity: "", low_stock_threshold: 5, description: "" };

export default function Products() {
  const [products, setProducts] = useState([]);
  const [search, setSearch] = useState("");
  const [lowStockOnly, setLowStockOnly] = useState(false);
  const [loading, setLoading] = useState(true);
  const [modalOpen, setModalOpen] = useState(false);
  const [editing, setEditing] = useState(null);
  const [form, setForm] = useState(emptyForm);
  const [formError, setFormError] = useState("");
  const [stockModal, setStockModal] = useState(null);
  const [stockChange, setStockChange] = useState("");
  const toast = useToast();

  async function load() {
    setLoading(true);
    const res = await api.get("/products", { params: { search: search || undefined, low_stock_only: lowStockOnly } });
    setProducts(res.data);
    setLoading(false);
  }

  useEffect(() => { load(); }, [lowStockOnly]); // eslint-disable-line

  function openCreate() {
    setEditing(null);
    setForm(emptyForm);
    setFormError("");
    setModalOpen(true);
  }

  function openEdit(p) {
    setEditing(p);
    setForm({
      name: p.name, category: p.category || "", price: p.price, quantity: p.quantity,
      low_stock_threshold: p.low_stock_threshold, description: p.description || "",
    });
    setFormError("");
    setModalOpen(true);
  }

  async function handleSubmit(e) {
    e.preventDefault();
    setFormError("");
    const payload = { ...form, price: Number(form.price), quantity: Number(form.quantity), low_stock_threshold: Number(form.low_stock_threshold) };
    try {
      if (editing) {
        await api.put(`/products/${editing.id}`, payload);
        toast("Product updated");
      } else {
        await api.post("/products", payload);
        toast("Product added");
      }
      setModalOpen(false);
      load();
    } catch (err) {
      setFormError(errorMessage(err));
    }
  }

  async function handleDelete(p) {
    if (!confirm(`Delete product "${p.name}"?`)) return;
    try {
      await api.delete(`/products/${p.id}`);
      toast("Product deleted");
      load();
    } catch (err) {
      toast(errorMessage(err), "error");
    }
  }

  async function handleStockAdjust(e) {
    e.preventDefault();
    try {
      await api.patch(`/products/${stockModal.id}/stock`, { change: Number(stockChange) });
      toast("Stock updated");
      setStockModal(null);
      setStockChange("");
      load();
    } catch (err) {
      toast(errorMessage(err), "error");
    }
  }

  return (
    <div>
      <div className="page-header">
        <h2>Products</h2>
        <button className="btn btn-primary" onClick={openCreate}>+ Add Product</button>
      </div>

      <div className="filters-row">
        <input placeholder="Search by name or category..." value={search} onChange={(e) => setSearch(e.target.value)}
               onKeyDown={(e) => e.key === "Enter" && load()} />
        <button className="btn btn-secondary btn-sm" onClick={load}>Search</button>
        <label style={{ display: "flex", alignItems: "center", gap: 6, fontSize: "0.85rem" }}>
          <input type="checkbox" checked={lowStockOnly} onChange={(e) => setLowStockOnly(e.target.checked)} />
          Low stock only
        </label>
      </div>

      <div className="table-wrap">
        <table>
          <thead>
            <tr><th>ID</th><th>Name</th><th>Category</th><th>Price</th><th>Stock</th><th></th></tr>
          </thead>
          <tbody>
            {loading && <tr><td colSpan={6} className="empty-state">Loading...</td></tr>}
            {!loading && products.length === 0 && <tr><td colSpan={6}><EmptyState title="No products found" hint="Add your first product to start tracking stock." /></td></tr>}
            {products.map((p) => (
              <tr key={p.id}>
                <td>#{p.id}</td>
                <td><div className="prod-cell"><ProductThumb category={p.category} /><span>{p.name}</span></div></td>
                <td>{p.category || "-"}</td>
                <td>₹{p.price}</td>
                <td>
                  {p.quantity} {p.low_stock && <span className="low-stock-tag">⚠ Low stock</span>}
                </td>
                <td>
                  <button className="btn btn-secondary btn-sm" onClick={() => setStockModal(p)}>Stock</button>{" "}
                  <button className="btn btn-secondary btn-sm" onClick={() => openEdit(p)}>Edit</button>{" "}
                  <button className="btn btn-danger btn-sm" onClick={() => handleDelete(p)}>Delete</button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {modalOpen && (
        <Modal title={editing ? "Edit Product" : "Add Product"} onClose={() => setModalOpen(false)}>
          <form onSubmit={handleSubmit}>
            <div className="form-grid">
              <div className="form-field full">
                <label>Product Name</label>
                <input value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} required />
              </div>
              <div className="form-field">
                <label>Category</label>
                <input value={form.category} onChange={(e) => setForm({ ...form, category: e.target.value })} />
              </div>
              <div className="form-field">
                <label>Price (₹)</label>
                <input type="number" step="0.01" min="0.01" value={form.price} onChange={(e) => setForm({ ...form, price: e.target.value })} required />
              </div>
              <div className="form-field">
                <label>Quantity</label>
                <input type="number" min="0" value={form.quantity} onChange={(e) => setForm({ ...form, quantity: e.target.value })} required />
              </div>
              <div className="form-field">
                <label>Low Stock Threshold</label>
                <input type="number" min="0" value={form.low_stock_threshold} onChange={(e) => setForm({ ...form, low_stock_threshold: e.target.value })} />
              </div>
              <div className="form-field full">
                <label>Description</label>
                <textarea rows={2} value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })} />
              </div>
            </div>
            {formError && <div className="form-error">{formError}</div>}
            <div className="modal-actions">
              <button type="button" className="btn btn-secondary" onClick={() => setModalOpen(false)}>Cancel</button>
              <button type="submit" className="btn btn-primary">{editing ? "Save Changes" : "Add Product"}</button>
            </div>
          </form>
        </Modal>
      )}

      {stockModal && (
        <Modal title={`Adjust Stock — ${stockModal.name}`} onClose={() => setStockModal(null)}>
          <p className="text-muted">Current stock: {stockModal.quantity}</p>
          <form onSubmit={handleStockAdjust}>
            <div className="form-field">
              <label>Change (use negative numbers to reduce, e.g. -5)</label>
              <input type="number" value={stockChange} onChange={(e) => setStockChange(e.target.value)} required />
            </div>
            <div className="modal-actions">
              <button type="button" className="btn btn-secondary" onClick={() => setStockModal(null)}>Cancel</button>
              <button type="submit" className="btn btn-primary">Update Stock</button>
            </div>
          </form>
        </Modal>
      )}
    </div>
  );
}
