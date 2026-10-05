import { useEffect, useRef, useState } from "react";
import api from "../api/client";
import { errorMessage } from "./Toast";

const STARTERS = ["Today's summary", "Low stock items", "Pending payments", "Top products"];

export default function ChatWidget() {
  const [open, setOpen] = useState(false);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const [messages, setMessages] = useState([
    { role: "assistant", content: "Hi! I'm your business assistant. Ask me about sales, stock, payments or customers." },
  ]);
  const [suggestions, setSuggestions] = useState(STARTERS);
  const endRef = useRef(null);
  const inputRef = useRef(null);

  useEffect(() => { endRef.current?.scrollIntoView({ behavior: "smooth" }); }, [messages, busy, open]);
  useEffect(() => { if (open) inputRef.current?.focus(); }, [open]);

  async function send(text) {
    const message = (text ?? input).trim();
    if (!message || busy) return;
    const history = messages.slice(-10).map(({ role, content }) => ({ role, content }));
    setMessages((m) => [...m, { role: "user", content: message }]);
    setInput("");
    setSuggestions([]);
    setBusy(true);
    try {
      const res = await api.post("/chat", { message, history });
      setMessages((m) => [...m, { role: "assistant", content: res.data.reply }]);
      setSuggestions(res.data.suggestions || []);
    } catch (err) {
      setMessages((m) => [...m, { role: "assistant", content: `Sorry, I couldn't answer that. ${errorMessage(err)}`, error: true }]);
      setSuggestions(STARTERS);
    } finally {
      setBusy(false);
    }
  }

  function reset() {
    setMessages([{ role: "assistant", content: "Chat cleared. What would you like to know?" }]);
    setSuggestions(STARTERS);
  }

  return (
    <>
      {open && (
        <section className="chat-panel" role="dialog" aria-label="Business assistant">
          <header className="chat-head">
            <img src="/images/bot-avatar.svg" alt="" />
            <div><strong>Business Assistant</strong><span><i className="chat-dot" /> Online · uses your live data</span></div>
            <button className="chat-icon" onClick={reset} title="Clear chat" aria-label="Clear chat">↺</button>
            <button className="chat-icon" onClick={() => setOpen(false)} title="Close" aria-label="Close chat">✕</button>
          </header>

          <div className="chat-body">
            {messages.map((m, i) => (
              <div key={i} className={`chat-row ${m.role}`}>
                {m.role === "assistant" && <img className="chat-av" src="/images/bot-avatar.svg" alt="" />}
                <div className={`chat-bubble ${m.error ? "error" : ""}`}>{m.content}</div>
              </div>
            ))}
            {busy && (
              <div className="chat-row assistant">
                <img className="chat-av" src="/images/bot-avatar.svg" alt="" />
                <div className="chat-bubble typing"><span /><span /><span /></div>
              </div>
            )}
            <div ref={endRef} />
          </div>

          {suggestions.length > 0 && !busy && (
            <div className="chat-chips">
              {suggestions.map((s) => <button key={s} onClick={() => send(s)}>{s}</button>)}
            </div>
          )}

          <form className="chat-input" onSubmit={(e) => { e.preventDefault(); send(); }}>
            <input ref={inputRef} value={input} onChange={(e) => setInput(e.target.value)} maxLength={1000}
                   placeholder="Ask about your business…" aria-label="Message" />
            <button type="submit" disabled={busy || !input.trim()} aria-label="Send">➤</button>
          </form>
        </section>
      )}

      <button className={`chat-fab ${open ? "open" : ""}`} onClick={() => setOpen((o) => !o)}
              aria-label={open ? "Close assistant" : "Open assistant"}>
        {open ? "✕" : <img src="/images/bot-avatar.svg" alt="" />}
      </button>
    </>
  );
}
