import { FormEvent, useCallback, useEffect, useMemo, useRef, useState } from "react";
import * as api from "./api";
import type { ChatMessage, ConversationDetail, ConversationSummary, Metrics, Operator } from "./types";

const DEMO_MODE = import.meta.env.VITE_DEMO_MODE !== "false";

function formatWhen(iso: string): string {
  try {
    return new Date(iso).toLocaleString("es-EC", { timeZone: "America/Guayaquil" });
  } catch {
    return iso;
  }
}

function commercialTone(state: string | null): string {
  if (state === "hot_lead") return "#8a4b12";
  if (state === "frustrated") return "#8f2d2d";
  if (state === "hesitant") return "#6b5a16";
  if (state === "interested") return "#0f6b57";
  return "#5c675f";
}

export function App() {
  const [token, setToken] = useState<string | null>(sessionStorage.getItem("operator_token"));
  const [operator, setOperator] = useState<Operator | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [connected, setConnected] = useState(false);
  const [items, setItems] = useState<ConversationSummary[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [detail, setDetail] = useState<ConversationDetail | null>(null);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [metrics, setMetrics] = useState<Metrics | null>(null);
  const [q, setQ] = useState("");
  const [attention, setAttention] = useState("");
  const [commercial, setCommercial] = useState("");
  const [drafts, setDrafts] = useState<Record<string, string>>({});
  const [demoText, setDemoText] = useState("Hola, me interesa el curso de phyton");
  const lastEventId = useRef(0);
  const selectedIdRef = useRef<string | null>(null);
  const threadRequest = useRef(0);

  const draft = selectedId ? drafts[selectedId] ?? "" : "";

  const loadList = useCallback(async (currentToken: string) => {
    const rows = await api.listConversations(currentToken, {
      q: q || undefined,
      attention_mode: attention || undefined,
      commercial_state: commercial || undefined,
    });
    setItems(rows);
  }, [attention, commercial, q]);

  const loadThread = useCallback(async (currentToken: string, id: string, requestId: number, replace: boolean) => {
    const [conv, msgs] = await Promise.all([api.getConversation(currentToken, id), api.listMessages(currentToken, id)]);
    if (threadRequest.current !== requestId || selectedIdRef.current !== id) return;
    setDetail(conv);
    setMessages((prev) => (replace ? [...msgs].sort((a, b) => a.seq - b.seq) : mergeMessages(prev, msgs)));
  }, []);

  useEffect(() => {
    if (!token) return;
    let cancelled = false;
    setLoading(true);
    Promise.all([loadList(token), api.getMetrics(token), api.me(token)])
      .then(([, m, profile]) => {
        if (!cancelled) {
          setMetrics(m);
          setOperator(profile);
        }
      })
      .catch((err: Error) => {
        if (!cancelled) setError(err.message);
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [token, loadList]);

  useEffect(() => {
    selectedIdRef.current = selectedId;
    if (!token || !selectedId) {
      setDetail(null);
      setMessages([]);
      return;
    }
    const requestId = ++threadRequest.current;
    setDetail(null);
    setMessages([]);
    loadThread(token, selectedId, requestId, true).catch((err: Error) => {
      if (threadRequest.current === requestId) setError(err.message);
    });
  }, [token, selectedId, loadThread]);

  useEffect(() => {
    if (!token) return;
    const abort = new AbortController();
    let stopped = false;
    const refresh = (conversationId: string | null) => {
      void loadList(token);
      void api.getMetrics(token).then(setMetrics);
      const openId = selectedIdRef.current;
      if (openId && (conversationId == null || conversationId === openId)) {
        void loadThread(token, openId, threadRequest.current, false);
      }
    };
    const connect = async () => {
      while (!stopped && !abort.signal.aborted) {
        try {
          setConnected(true);
          await api.streamEvents(
            token,
            lastEventId.current,
            (event) => {
              lastEventId.current = Math.max(lastEventId.current, event.id);
              refresh(event.conversation_id);
            },
            abort.signal,
          );
          setConnected(false);
        } catch {
          if (abort.signal.aborted) return;
          setConnected(false);
        }
        if (!stopped) await new Promise((resolve) => setTimeout(resolve, 1200));
      }
    };
    void connect();
    return () => {
      stopped = true;
      abort.abort();
    };
  }, [token, loadList, loadThread]);

  async function onLogin(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);
    const form = new FormData(event.currentTarget);
    try {
      const result = await api.login(String(form.get("email")), String(form.get("password")));
      sessionStorage.setItem("operator_token", result.access_token);
      setToken(result.access_token);
      setOperator(result.operator);
    } catch (err) {
      setError(err instanceof Error ? err.message : "No se pudo iniciar sesión");
    }
  }

  async function onSend(event: FormEvent) {
    event.preventDefault();
    if (!token || !selectedId || !draft.trim()) return;
    setError(null);
    try {
      const chatId = selectedId;
      const saved = await api.sendMessage(token, chatId, draft.trim());
      if (selectedIdRef.current === chatId) {
        setMessages((prev) => mergeMessages(prev, [saved]));
      }
      setDrafts((prev) => ({ ...prev, [chatId]: "" }));
      await loadList(token);
    } catch (err) {
      setError(err instanceof Error ? err.message : "No se pudo enviar");
    }
  }

  async function runAction(kind: "takeover" | "resume" | "close") {
    if (!token || !selectedId) return;
    setError(null);
    try {
      if (kind === "takeover") await api.takeover(token, selectedId);
      if (kind === "resume") await api.resumeAi(token, selectedId);
      if (kind === "close") await api.closeConversation(token, selectedId);
      if (selectedIdRef.current === selectedId) {
        await loadThread(token, selectedId, threadRequest.current, false);
      }
      await loadList(token);
    } catch (err) {
      setError(err instanceof Error ? err.message : "No se pudo completar la acción");
    }
  }

  async function sendDemo() {
    if (!token) return;
    setError(null);
    try {
      await api.sendDemoInbound(token, demoText);
      await loadList(token);
    } catch (err) {
      setError(err instanceof Error ? err.message : "No se pudo simular el mensaje");
    }
  }

  const selected = useMemo(() => items.find((item) => item.id === selectedId) || detail, [items, selectedId, detail]);

  if (!token) {
    return (
      <div className="login">
        <form onSubmit={onLogin}>
          <h1>Tablero de asesoría educativa</h1>
          <p className="hint">Acceso para operadores. Los textos de la interfaz están en español.</p>
          {DEMO_MODE && (
            <p className="hint">
              Demo local: operador@demo.local / demo-operador. Adaptadores simulados, no hay Telegram real.
            </p>
          )}
          <label>
            Correo
            <input name="email" type="email" autoComplete="username" defaultValue={DEMO_MODE ? "operador@demo.local" : ""} required />
          </label>
          <label>
            Contraseña
            <input name="password" type="password" autoComplete="current-password" defaultValue={DEMO_MODE ? "demo-operador" : ""} required />
          </label>
          {error && <p className="error" role="alert">{error}</p>}
          <button type="submit">Entrar</button>
        </form>
      </div>
    );
  }

  return (
    <div className="shell">
      <header className="topbar">
        <div>
          <strong>Centro de capacitación (demostración)</strong>
          <div className="meta">
            <span className="badge" style={{ color: connected ? "#0f6b57" : "#8f2d2d" }}>
              <span className="dot" aria-hidden="true" />
              {connected ? "Eventos en vivo conectados" : "Reconectando eventos"}
            </span>
            <span>{operator?.display_name || "Operador"}</span>
          </div>
        </div>
        <button
          className="secondary"
          type="button"
          onClick={() => {
            sessionStorage.removeItem("operator_token");
            setToken(null);
          }}
        >
          Cerrar sesión
        </button>
      </header>
      <div className="layout">
        <section className="col" aria-label="Lista de conversaciones">
          <div className="filters">
            <label>
              Buscar
              <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Nombre o chat" />
            </label>
            <label>
              Modo de atención
              <select value={attention} onChange={(e) => setAttention(e.target.value)}>
                <option value="">Todos</option>
                <option value="ai_active">Atención automática</option>
                <option value="human_pending">Pendiente de asesor</option>
                <option value="human_active">Asesor en control</option>
                <option value="closed">Cerrada</option>
              </select>
            </label>
            <label>
              Estado comercial
              <select value={commercial} onChange={(e) => setCommercial(e.target.value)}>
                <option value="">Todos</option>
                <option value="interested">Interesado</option>
                <option value="hesitant">Dudoso</option>
                <option value="frustrated">Frustrado</option>
                <option value="hot_lead">Lead caliente</option>
              </select>
            </label>
          </div>
          {loading && <p className="empty">Cargando conversaciones…</p>}
          {!loading && items.length === 0 && <p className="empty">No hay conversaciones con esos filtros.</p>}
          {items.map((item) => (
            <article
              key={item.id}
              className={`item panel ${selectedId === item.id ? "active" : ""}`}
              onClick={() => setSelectedId(item.id)}
              onKeyDown={(e) => e.key === "Enter" && setSelectedId(item.id)}
              tabIndex={0}
              role="button"
              aria-current={selectedId === item.id}
            >
              <strong>{item.contact_name}</strong>
              <div className="meta">
                <span className="badge">
                  {item.attention_label}
                </span>
                <span className="badge" style={{ color: commercialTone(item.commercial_state) }}>
                  <span className="dot" aria-hidden="true" />
                  {item.commercial_label}
                </span>
                {item.unread_count > 0 && <span className="badge">{item.unread_count} sin leer</span>}
              </div>
              <p className="hint">{formatWhen(item.last_activity_at)}</p>
            </article>
          ))}
        </section>
        <section className="col" aria-label="Historial del chat">
          {!selected && <p className="empty">Selecciona una conversación para ver el historial.</p>}
          {selected && (
            <>
              <div className="panel">
                <strong>{selected.contact_name}</strong>
                <p className="meta">
                  <span>{selected.attention_label}</span>
                  <span>{selected.commercial_label}</span>
                </p>
              </div>
              {messages.map((message) => (
                <article key={message.id} className={`msg ${message.authorship}`}>
                  <div className="meta">
                    <span>{message.authorship_label}</span>
                    <span>{formatWhen(message.created_at)}</span>
                    <span>{message.delivery_status_label}</span>
                  </div>
                  <p>{message.body}</p>
                </article>
              ))}
              {messages.length === 0 && <p className="empty">Aún no hay mensajes en este hilo.</p>}
              <form className="composer" onSubmit={onSend}>
                <label className="sr-only" htmlFor="draft">
                  Respuesta del asesor
                </label>
                <textarea
                  id="draft"
                  value={draft}
                  onChange={(e) => selectedId && setDrafts((prev) => ({ ...prev, [selectedId]: e.target.value }))}
                  placeholder="Escribe al prospecto. Enviar toma el control si aún no lo tienes."
                  rows={3}
                />
                <button type="submit">Enviar como asesor</button>
              </form>
            </>
          )}
        </section>
        <section className="col" aria-label="Perfil y control">
          {detail ? (
            <div className="panel">
              <h2>Perfil del prospecto</h2>
              <p><strong>Interés:</strong> {detail.lead_profile.interested_course_name || detail.lead_profile.interest_area || "Sin definir"}</p>
              <p><strong>Experiencia:</strong> {detail.lead_profile.experience_level || "No indicada"}</p>
              <p><strong>Objetivo:</strong> {detail.lead_profile.learning_goal || "No indicado"}</p>
              <p><strong>Modalidad:</strong> {detail.lead_profile.preferred_modality || "No indicada"}</p>
              <h3>Resumen para el operador</h3>
              <p>{detail.operator_summary || "Todavía no hay resumen. Aparece al transferir o cuando el historial lo requiere."}</p>
              <p><strong>Motivo de transferencia:</strong> {detail.transfer_reason || "Ninguno"}</p>
              <p className="hint">Asesor asignado: {detail.assigned_operator_name || "Nadie"} · revisión {detail.control_version}</p>
              <div className="status-row">
                <button type="button" onClick={() => runAction("takeover")}>Tomar control</button>
                <button className="secondary" type="button" onClick={() => runAction("resume")}>Reanudar IA</button>
                <button className="danger" type="button" onClick={() => runAction("close")}>Cerrar conversación</button>
              </div>
            </div>
          ) : (
            <p className="empty">El perfil aparece al abrir un chat.</p>
          )}
          {DEMO_MODE && (
            <div className="demo-box">
              <strong>Canal simulado de Telegram</strong>
              <p className="hint">No llama a Telegram. Envía un mensaje como si llegara el webhook.</p>
              <textarea value={demoText} onChange={(e) => setDemoText(e.target.value)} rows={3} />
              <button type="button" className="secondary" onClick={sendDemo}>Simular mensaje entrante</button>
            </div>
          )}
        </section>
      </div>
      <footer className="metrics" aria-label="Métricas">
        {metrics ? (
          <>
            <span title={metrics.definitions.active_conversations}>Activas: {metrics.active_conversations}</span>
            <span title={metrics.definitions.human_pending}>Pendientes humanas: {metrics.human_pending}</span>
            <span title={metrics.definitions.hot_leads}>Leads calientes: {metrics.hot_leads}</span>
            <span title={metrics.definitions.enrollment_requests}>Solicitudes de inscripción: {metrics.enrollment_requests}</span>
            <span title={metrics.definitions.median_first_response_ms}>
              Mediana primera respuesta: {metrics.median_first_response_ms == null ? "sin datos" : `${metrics.median_first_response_ms} ms`}
            </span>
          </>
        ) : (
          <span>Cargando métricas…</span>
        )}
        {error && <span className="error" role="alert">{error}</span>}
      </footer>
    </div>
  );
}

function mergeMessages(previous: ChatMessage[], incoming: ChatMessage[]): ChatMessage[] {
  const map = new Map<string, ChatMessage>();
  for (const item of previous) map.set(item.id, item);
  for (const item of incoming) map.set(item.id, item);
  return [...map.values()].sort((a, b) => a.seq - b.seq);
}
