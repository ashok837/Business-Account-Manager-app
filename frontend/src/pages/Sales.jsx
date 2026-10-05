import { useEffect, useState } from "react";
import api from "../api/client";
import Badge from "../components/Badge";

export default function Sales() {
  const [sales, setSales] = useState([]);
  const [customers, setCustomers] = useState([]);
  const [products, setProducts] = useState([]);
  const [customerId, setCustomerId] = useState("");
  const [productId, setProductId] = useState("");
  const [paymentStatus, setPaymentStatus] = useState("");
  const [loading, setLoading] = useState(true);

  async function load() {
    setLoading(true);
    const res = await api.get("/sales", {
      params: {
        customer_id: customerId || undefined,
        product_id: productId || undefined,
        payment_status: paymentStatus || undefined,
      },
    });
    setSales(res.data);
    setLoading(false);
  }

  useEffect(() => {
    api.get("/customers").then((r) => setCustomers(r.data));
    api.get("/products").then((r) => setProducts(r.data));
    load();
  }, []); // eslint-disable-line

  useEffect(() => { load(); }, [customerId, productId, paymentStatus]); // eslint-disable-line

  const total = sales.reduce((s, x) => s + x.total_amount, 0);

  return (
    <div>
      <div className="page-header"><h2>Sales</h2></div>

      <div className="filters-row">
        <select value={customerId} onChange={(e) => setCustomerId(e.target.value)}>
          <option value="">All Customers</option>
          {customers.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
        </select>
        <select value={productId} onChange={(e) => setProductId(e.target.value)}>
          <option value="">All Products</option>
          {products.map((p) => <option key={p.id} value={p.id}>{p.name}</option>)}
        </select>
        <select value={paymentStatus} onChange={(e) => setPaymentStatus(e.target.value)}>
          <option value="">All Payment Statuses</option>
          <option value="Pending">Pending</option>
          <option value="Partially Paid">Partially Paid</option>
          <option value="Paid">Paid</option>
        </select>
      </div>

      <div className="table-wrap">
        <table>
          <thead>
            <tr><th>Sale ID</th><th>Order</th><th>Customer</th><th>Product</th><th>Qty</th><th>Unit Price</th><th>Total</th><th>Date</th><th>Payment</th></tr>
          </thead>
          <tbody>
            {loading && <tr><td colSpan={9} className="empty-state">Loading...</td></tr>}
            {!loading && sales.length === 0 && <tr><td colSpan={9} className="empty-state">No sales found</td></tr>}
            {sales.map((s) => (
              <tr key={s.id}>
                <td>#{s.id}</td>
                <td>#{s.order_id}</td>
                <td>{s.customer_name}</td>
                <td>{s.product_name}</td>
                <td>{s.quantity}</td>
                <td>₹{s.unit_price}</td>
                <td>₹{s.total_amount}</td>
                <td>{new Date(s.date).toLocaleDateString()}</td>
                <td><Badge value={s.payment_status} /></td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {!loading && sales.length > 0 && (
        <p style={{ textAlign: "right", fontWeight: 700, marginTop: 10 }}>Total: ₹{total.toFixed(2)}</p>
      )}
    </div>
  );
}
