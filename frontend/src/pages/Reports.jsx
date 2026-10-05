import { useState } from "react";
import api, { API_URL } from "../api/client";

const REPORT_TABS = [
  { key: "sales", label: "Sales" },
  { key: "expenses", label: "Expenses" },
  { key: "profit", label: "Profit" },
  { key: "customers", label: "Customers" },
  { key: "products", label: "Products / Stock" },
  { key: "payments", label: "Payments" },
];

export default function Reports() {
  const [tab, setTab] = useState("sales");
  const [dateFrom, setDateFrom] = useState("");
  const [dateTo, setDateTo] = useState("");
  const [period, setPeriod] = useState("");
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(false);

  async function runReport() {
    setLoading(true);
    const params = {};
    if (dateFrom) params.date_from = dateFrom;
    if (dateTo) params.date_to = dateTo;
    if (period && tab === "sales") params.period = period;
    const res = await api.get(`/reports/${tab}`, { params });
    setData(res.data);
    setLoading(false);
  }

  function downloadCsv() {
    const token = localStorage.getItem("token");
    const params = new URLSearchParams();
    if (dateFrom) params.set("date_from", dateFrom);
    if (dateTo) params.set("date_to", dateTo);
    if (period && tab === "sales") params.set("period", period);
    params.set("export", "csv");
    // Use fetch so we can attach the auth header, then trigger a browser download
    fetch(`${API_URL}/reports/${tab}?${params.toString()}`, {
      headers: { Authorization: `Bearer ${token}` },
    })
      .then((r) => r.blob())
      .then((blob) => {
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement("a");
        a.href = url;
        a.download = `${tab}_report.csv`;
        a.click();
        window.URL.revokeObjectURL(url);
      });
  }

  function renderTable() {
    if (!data) return <div className="empty-state">Choose filters and click "Run Report"</div>;

    if (tab === "sales") {
      return (
        <>
          <p style={{ fontWeight: 700 }}>Total Sales: ₹{data.total_sales} ({data.count} line items)</p>
          <div className="table-wrap">
            <table>
              <thead><tr><th>Date</th><th>Order</th><th>Customer</th><th>Product</th><th>Qty</th><th>Total</th><th>Payment</th></tr></thead>
              <tbody>
                {data.items.map((r, i) => (
                  <tr key={i}>
                    <td>{new Date(r.date).toLocaleDateString()}</td><td>#{r.order_id}</td><td>{r.customer}</td>
                    <td>{r.product}</td><td>{r.quantity}</td><td>₹{r.total}</td><td>{r.payment_status}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      );
    }
    if (tab === "expenses") {
      return (
        <>
          <p style={{ fontWeight: 700 }}>Total Expenses: ₹{data.total_expenses}</p>
          <div className="table-wrap">
            <table>
              <thead><tr><th>Date</th><th>Category</th><th>Description</th><th>Amount</th><th>Method</th></tr></thead>
              <tbody>
                {data.items.map((r) => (
                  <tr key={r.id}><td>{new Date(r.date).toLocaleDateString()}</td><td>{r.category}</td><td>{r.description || "-"}</td><td>₹{r.amount}</td><td>{r.payment_method}</td></tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      );
    }
    if (tab === "profit") {
      return (
        <div className="stat-grid">
          <div className="stat-card accent-success"><div className="label">Total Revenue</div><div className="value">₹{data.total_revenue}</div></div>
          <div className="stat-card accent-danger"><div className="label">Total Expenses</div><div className="value">₹{data.total_expenses}</div></div>
          <div className="stat-card accent-primary"><div className="label">Net Profit</div><div className="value">₹{data.net_profit}</div></div>
        </div>
      );
    }
    if (tab === "customers") {
      return (
        <div className="table-wrap">
          <table>
            <thead><tr><th>Customer</th><th>Orders</th><th>Total Spent</th><th>Paid</th><th>Outstanding</th></tr></thead>
            <tbody>
              {data.map((r) => (
                <tr key={r.customer_id}><td>{r.name}</td><td>{r.total_orders}</td><td>₹{r.total_spent}</td><td>₹{r.total_paid}</td><td>₹{r.outstanding_balance}</td></tr>
              ))}
            </tbody>
          </table>
        </div>
      );
    }
    if (tab === "products") {
      return (
        <div className="table-wrap">
          <table>
            <thead><tr><th>Product</th><th>Category</th><th>Stock</th><th>Units Sold</th><th>Revenue</th></tr></thead>
            <tbody>
              {data.map((r) => (
                <tr key={r.product_id}>
                  <td>{r.name}</td><td>{r.category || "-"}</td>
                  <td>{r.current_stock} {r.low_stock && <span className="low-stock-tag">⚠</span>}</td>
                  <td>{r.units_sold}</td><td>₹{r.revenue}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      );
    }
    if (tab === "payments") {
      return (
        <>
          <p style={{ fontWeight: 700 }}>Total Collected: ₹{data.total_collected}</p>
          <div className="table-wrap">
            <table>
              <thead><tr><th>Date</th><th>Customer</th><th>Order</th><th>Amount</th><th>Method</th><th>Status</th></tr></thead>
              <tbody>
                {data.items.map((r) => (
                  <tr key={r.id}><td>{new Date(r.date).toLocaleDateString()}</td><td>{r.customer}</td><td>#{r.order_id}</td><td>₹{r.amount}</td><td>{r.method}</td><td>{r.status}</td></tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      );
    }
    return null;
  }

  const supportsCsv = ["sales", "expenses", "payments"].includes(tab);

  return (
    <div>
      <div className="page-header"><h2>Reports</h2></div>

      <div className="filters-row" style={{ marginBottom: 6 }}>
        {REPORT_TABS.map((t) => (
          <button key={t.key} className={`btn btn-sm ${tab === t.key ? "btn-primary" : "btn-secondary"}`}
                  onClick={() => { setTab(t.key); setData(null); }}>
            {t.label}
          </button>
        ))}
      </div>

      <div className="filters-row">
        {tab === "sales" && (
          <select value={period} onChange={(e) => setPeriod(e.target.value)}>
            <option value="">Custom range</option>
            <option value="daily">Today</option>
            <option value="weekly">This Week</option>
            <option value="monthly">This Month</option>
          </select>
        )}
        {tab !== "customers" && tab !== "products" && (
          <>
            <input type="date" value={dateFrom} onChange={(e) => setDateFrom(e.target.value)} />
            <span className="text-muted">to</span>
            <input type="date" value={dateTo} onChange={(e) => setDateTo(e.target.value)} />
          </>
        )}
        <button className="btn btn-primary btn-sm" onClick={runReport} disabled={loading}>
          {loading ? "Running..." : "Run Report"}
        </button>
        {supportsCsv && data && (
          <button className="btn btn-secondary btn-sm" onClick={downloadCsv}>Export CSV</button>
        )}
      </div>

      {renderTable()}
    </div>
  );
}
