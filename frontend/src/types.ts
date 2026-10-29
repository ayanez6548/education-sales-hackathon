export type Operator = {
  id: string;
  email: string;
  display_name: string;
  role: string;
};

export type ConversationSummary = {
  id: string;
  contact_name: string;
  preferred_name: string | null;
  attention_mode: string;
  attention_label: string;
  commercial_state: string | null;
  commercial_label: string;
  commercial_confidence: number | null;
  last_activity_at: string;
  unread_count: number;
  assigned_operator_id: string | null;
  assigned_operator_name: string | null;
  control_version: number;
};

export type LeadProfile = {
  interest_area: string | null;
  experience_level: string | null;
  learning_goal: string | null;
  availability: string | null;
  preferred_modality: string | null;
  budget_note: string | null;
  interested_course_id: string | null;
  interested_course_name: string | null;
};

export type ConversationDetail = ConversationSummary & {
  operator_summary: string | null;
  transfer_reason: string | null;
  commercial_reason: string | null;
  classified_at: string | null;
  lead_profile: LeadProfile;
  telegram_chat_id: string;
  closed_at: string | null;
};

export type ChatMessage = {
  id: string;
  seq: number;
  direction: string;
  authorship: string;
  authorship_label: string;
  body: string;
  delivery_status: string;
  delivery_status_label: string;
  created_at: string;
  operator_id: string | null;
};

export type Metrics = {
  active_conversations: number;
  human_pending: number;
  hot_leads: number;
  enrollment_requests: number;
  median_first_response_ms: number | null;
  definitions: Record<string, string>;
};
