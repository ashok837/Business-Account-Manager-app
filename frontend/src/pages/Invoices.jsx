import { useEffect, useState } from "react";
import jsPDF from "jspdf";
import autoTable from "jspdf-autotable";
import api from "../api/client";
import Modal from "../components/Modal";
import Badge from "../components/Badge";
import { useToast, errorMessage } from "../components/Toast";

export default function Invoices() {
  const [invoices, setInvoices] = useState([]);
  const [orders, setOrders] = useState([]);
  const [loading, setLoading] = useState(true);
  const [modalOpen, setModalOpen] = useState(false);
  const [orderId, setOrderId] = useState("");
  const [discount, setDiscount] = useState(0);
  const [taxPercent, setTaxPercent] = useState(0);
  const [formError, setFormError] = useState("");
  const [viewInvoice, setViewInvoice] = useState(null);
  const [business, setBusiness] = useState({ name: "", address: "", gst: "" });
  const toast = useToast();

  async function load() {
    setLoading(true);
    const [inv, biz] = await Promise.all([api.get("/invoices"), api.get("/invoices/business/info")]);
    setInvoices(inv.data);
    setBusiness(biz.data);
    setLoading(false);
  }

  useEffect(() => { load(); }, []);

  async function openCreate() {
    const [ordersRes, existingRes] = await Promise.all([api.get("/orders"), api.get("/invoices")]);
    const invoicedOrderIds = new Set(existingRes.data.map((i) => i.order_id));
    setOrders(ordersRes.data.filter((o) => !invoicedOrderIds.has(o.id) && o.status !== "Cancelled"));
    setOrderId("");
    setDiscount(0);
    setTaxPercent(0);
    setFormError("");
    setModalOpen(true);
  }

  async function handleSubmit(e) {
    e.preventDefault();
    setFormError("");
    try {
      const res = await api.post("/invoices", { order_id: Number(orderId), discount: Number(discount), tax_percent: Number(taxPercent) });
      toast("Invoice generated");
      setModalOpen(false);
      load();
      setViewInvoice(res.data);
    } catch (err) {
      setFormError(errorMessage(err));
    }
  }

  function buildPdf(invoice) {
    const doc = new jsPDF();
    doc.setFontSize(16);
    doc.text(business.name || "Business Name", 14, 18);
    doc.setFontSize(10);
    doc.text(business.address || "", 14, 25);
    if (business.gst) doc.text(`GSTIN: ${business.gst}`, 14, 30);

    doc.setFontSize(12);
    doc.text(`Invoice #: ${invoice.invoice_number}`, 140, 18);
    doc.text(`Date: ${new Date(invoice.invoice_date).toLocaleDateString()}`, 140, 24);

    doc.setFontSize(11);
    doc.text("Bill To:", 14, 42);
    doc.setFontSize(10);
    doc.text(invoice.customer?.name || "-", 14, 48);
    doc.text(invoice.customer?.phone || "-", 14, 53);
    if (invoice.customer?.address) doc.text(invoice.customer.address, 14, 58);

    autoTable(doc, {
      startY: 66,
      head: [["Product", "Quantity", "Price", "Line Total"]],
      body: invoice.items.map((i) => [i.product_name, i.quantity, `Rs. ${i.unit_price}`, `Rs. ${i.line_total}`]),
    });

    const finalY = doc.lastAutoTable.finalY + 10;
    doc.text(`Subtotal: Rs. ${invoice.subtotal}`, 140, finalY);
    doc.text(`Discount: Rs. ${invoice.discount}`, 140, finalY + 6);
    doc.text(`Tax (${invoice.tax_percent}%): Rs. ${invoice.tax_amount}`, 140, finalY + 12);
    doc.setFontSize(12);
    doc.text(`Grand Total: Rs. ${invoice.grand_total}`, 140, finalY + 20);
    doc.setFontSize(10);
    doc.text(`Payment Status: ${invoice.payment_status || "-"}`, 14, finalY + 20);

    return doc;
  }

  function downloadPdf(invoice) {
    buildPdf(invoice).save(`${invoice.invoice_number}.pdf`);
  }

  function printInvoice(invoice) {
    const doc = buildPdf(invoice);
    doc.autoPrint();
    window.open(doc.output("bloburl"), "_blank");
  }

  return (
    <div>
      <div className="page-header">
        <h2>Invoices</h2>
        <button className="btn btn-primary" onClick={openCreate}>+ Generate Invoice</button>
      </div>

      <div className="table-wrap">
        <table>
          <thead>
            <tr><th>Invoice #</th><th>Order</th><th>Customer</th><th>Grand Total</th><th>Date</th><th>Payment</th><th></th></tr>
          </thead>
          <tbody>
            {loading && <tr><td colSpan={7} className="empty-state">Loading...</td></tr>}
            {!loading && invoices.length === 0 && <tr><td colSpan={7} className="empty-state">No invoices generated yet</td></tr>}
            {invoices.map((inv) => (
              <tr key={inv.id}>
                <td>{inv.invoice_number}</td>
                <td>#{inv.order_id}</td>
                <td>{inv.customer?.name}</td>
                <td>₹{inv.grand_total}</td>
                <td>{new Date(inv.invoice_date).toLocaleDateString()}</td>
                <td>{inv.payment_status && <Badge value={inv.payment_status} />}</td>
                <td>
                  <button className="btn btn-secondary btn-sm" onClick={() => setViewInvoice(inv)}>View</button>{" "}
                  <button className="btn btn-secondary btn-sm" onClick={() => printInvoice(inv)}>Print</button>{" "}
                  <button className="btn btn-secondary btn-sm" onClick={() => downloadPdf(inv)}>PDF</button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {modalOpen && (
        <Modal title="Generate Invoice" onClose={() => setModalOpen(false)}>
          <form onSubmit={handleSubmit}>
            <div className="form-field full">
              <label>Order</label>
              <select value={orderId} onChange={(e) => setOrderId(e.target.value)} required>
                <option value="">Select an order without an invoice...</option>
                {orders.map((o) => (
                  <option key={o.id} value={o.id}>#{o.id} — {o.customer_name} — ₹{o.total_amount}</option>
                ))}
              </select>
            </div>
            <div className="form-grid">
              <div className="form-field">
                <label>Discount (₹)</label>
                <input type="number" step="0.01" min="0" value={discount} onChange={(e) => setDiscount(e.target.value)} />
              </div>
              <div className="form-field">
                <label>Tax / GST (%)</label>
                <input type="number" step="0.01" min="0" value={taxPercent} onChange={(e) => setTaxPercent(e.target.value)} />
              </div>
            </div>
            {formError && <div className="form-error">{formError}</div>}
            <div className="modal-actions">
              <button type="button" className="btn btn-secondary" onClick={() => setModalOpen(false)}>Cancel</button>
              <button type="submit" className="btn btn-primary">Generate Invoice</button>
            </div>
          </form>
        </Modal>
      )}

      {viewInvoice && (
        <Modal title={viewInvoice.invoice_number} onClose={() => setViewInvoice(null)}>
          <p><strong>{business.name}</strong><br />{business.address}</p>
          <p><strong>Bill To:</strong> {viewInvoice.customer?.name} — {viewInvoice.customer?.phone}</p>
          <div className="table-wrap">
            <table>
              <thead><tr><th>Product</th><th>Qty</th><th>Price</th><th>Total</th></tr></thead>
              <tbody>
                {viewInvoice.items.map((i) => (
                  <tr key={i.id}><td>{i.product_name}</td><td>{i.quantity}</td><td>₹{i.unit_price}</td><td>₹{i.line_total}</td></tr>
                ))}
              </tbody>
            </table>
          </div>
          <p style={{ textAlign: "right", marginTop: 10 }}>Subtotal: ₹{viewInvoice.subtotal}</p>
          <p style={{ textAlign: "right" }}>Discount: ₹{viewInvoice.discount}</p>
          <p style={{ textAlign: "right" }}>Tax ({viewInvoice.tax_percent}%): ₹{viewInvoice.tax_amount}</p>
          <p style={{ textAlign: "right", fontWeight: 700, fontSize: "1.1rem" }}>Grand Total: ₹{viewInvoice.grand_total}</p>
          <div className="modal-actions">
            <button className="btn btn-secondary" onClick={() => printInvoice(viewInvoice)}>Print</button>
            <button className="btn btn-secondary" onClick={() => downloadPdf(viewInvoice)}>Download PDF</button>
            <button className="btn btn-primary" onClick={() => setViewInvoice(null)}>Close</button>
          </div>
        </Modal>
      )}
    </div>
  );
}
