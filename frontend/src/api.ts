import type { ChatMessage, ConversationDetail, ConversationSummary, Metrics, Operator } from "./types";

const API_URL = import.meta.env.VITE_API_URL || "http://localhost:8000";

function headers(token: string, extra?: Record<string, string>): HeadersInit {
  return {
    Authorization: `Bearer ${token}`,
    "Content-Type": "application/json",
    ...extra,
  };
}

async function parseError(response: Response): Promise<string> {
  try {
    const body = await response.json();
    if (typeof body.detail === "string") return body.detail;
    return JSON.stringify(body.detail || body);
  } catch {
    return `Error HTTP ${response.status}`;
  }
}

export async function me(token: string): Promise<Operator> {
  const response = await fetch(`${API_URL}/api/me`, { headers: headers(token) });
  if (!response.ok) throw new Error(await parseError(response));
  return response.json();
}

export async function login(email: string, password: string): Promise<{ access_token: string; operator: Operator }> {
  const response = await fetch(`${API_URL}/api/auth/login`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, password }),
  });
  if (!response.ok) throw new Error(await parseError(response));
  return response.json();
}

export async function listConversations(
  token: string,
  query: { q?: string; attention_mode?: string; commercial_state?: string },
): Promise<ConversationSummary[]> {
  const params = new URLSearchParams();
  if (query.q) params.set("q", query.q);
  if (query.attention_mode) params.set("attention_mode", query.attention_mode);
  if (query.commercial_state) params.set("commercial_state", query.commercial_state);
  const response = await fetch(`${API_URL}/api/conversations?${params.toString()}`, { headers: headers(token) });
  if (!response.ok) throw new Error(await parseError(response));
  return response.json();
}

export async function getConversation(token: string, id: string): Promise<ConversationDetail> {
  const response = await fetch(`${API_URL}/api/conversations/${id}`, { headers: headers(token) });
  if (!response.ok) throw new Error(await parseError(response));
  return response.json();
}

export async function listMessages(token: string, id: string, afterSeq = 0): Promise<ChatMessage[]> {
  const response = await fetch(`${API_URL}/api/conversations/${id}/messages?after_seq=${afterSeq}`, {
    headers: headers(token),
  });
  if (!response.ok) throw new Error(await parseError(response));
  const body = await response.json();
  return body.items;
}

export async function takeover(token: string, id: string): Promise<void> {
  const response = await fetch(`${API_URL}/api/conversations/${id}/takeover`, {
    method: "POST",
    headers: headers(token, { "Idempotency-Key": crypto.randomUUID() }),
  });
  if (!response.ok) throw new Error(await parseError(response));
}

export async function resumeAi(token: string, id: string): Promise<void> {
  const response = await fetch(`${API_URL}/api/conversations/${id}/resume`, {
    method: "POST",
    headers: headers(token, { "Idempotency-Key": crypto.randomUUID() }),
  });
  if (!response.ok) throw new Error(await parseError(response));
}

export async function closeConversation(token: string, id: string): Promise<void> {
  const response = await fetch(`${API_URL}/api/conversations/${id}/close`, {
    method: "POST",
    headers: headers(token, { "Idempotency-Key": crypto.randomUUID() }),
  });
  if (!response.ok) throw new Error(await parseError(response));
}

export async function sendMessage(token: string, id: string, body: string): Promise<ChatMessage> {
  const response = await fetch(`${API_URL}/api/conversations/${id}/messages`, {
    method: "POST",
    headers: headers(token, { "Idempotency-Key": crypto.randomUUID() }),
    body: JSON.stringify({ body }),
  });
  if (!response.ok) throw new Error(await parseError(response));
  return response.json();
}

export async function getMetrics(token: string): Promise<Metrics> {
  const response = await fetch(`${API_URL}/api/metrics`, { headers: headers(token) });
  if (!response.ok) throw new Error(await parseError(response));
  return response.json();
}

export async function sendDemoInbound(token: string, text: string, chatId = "10001"): Promise<void> {
  const response = await fetch(`${API_URL}/api/demo/telegram/inbound`, {
    method: "POST",
    headers: headers(token),
    body: JSON.stringify({
      text,
      telegram_user_id: chatId,
      telegram_chat_id: chatId,
      display_name: "Prospecto Demo",
    }),
  });
  if (!response.ok) throw new Error(await parseError(response));
}

export type LiveEvent = {
  id: number;
  event_type: string;
  conversation_id: string | null;
  payload: Record<string, unknown>;
};

export async function streamEvents(
  token: string,
  afterId: number,
  onEvent: (event: LiveEvent) => void,
  signal: AbortSignal,
): Promise<void> {
  const response = await fetch(`${API_URL}/api/events?after_id=${afterId}`, {
    headers: { Authorization: `Bearer ${token}`, Accept: "text/event-stream" },
    signal,
  });
  if (!response.ok || !response.body) {
    throw new Error(await parseError(response));
  }
  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  while (!signal.aborted) {
    const { value, done } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    const chunks = buffer.split("\n\n");
    buffer = chunks.pop() ?? "";
    for (const chunk of chunks) {
      const parsed = parseSseChunk(chunk);
      if (parsed) onEvent(parsed);
    }
  }
}

function parseSseChunk(chunk: string): LiveEvent | null {
  let eventType = "message";
  let data = "";
  let id = 0;
  for (const line of chunk.split("\n")) {
    if (line.startsWith("event:")) eventType = line.slice(6).trim();
    if (line.startsWith("data:")) data += line.slice(5).trim();
    if (line.startsWith("id:")) id = Number(line.slice(3).trim() || "0");
  }
  if (!data) return null;
  try {
    const payload = JSON.parse(data) as LiveEvent;
    return {
      id: payload.id || id,
      event_type: payload.event_type || eventType,
      conversation_id: payload.conversation_id ?? null,
      payload: payload.payload ?? {},
    };
  } catch {
    return null;
  }
}

export { API_URL };
