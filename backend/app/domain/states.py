from enum import StrEnum


class AttentionMode(StrEnum):
    AI_ACTIVE = "ai_active"
    HUMAN_PENDING = "human_pending"
    HUMAN_ACTIVE = "human_active"
    CLOSED = "closed"


class CommercialState(StrEnum):
    INTERESTED = "interested"
    HESITANT = "hesitant"
    FRUSTRATED = "frustrated"
    HOT_LEAD = "hot_lead"


COMMERCIAL_LABELS = {
    CommercialState.INTERESTED: "Interesado",
    CommercialState.HESITANT: "Dudoso",
    CommercialState.FRUSTRATED: "Frustrado",
    CommercialState.HOT_LEAD: "Lead caliente",
}

ATTENTION_LABELS = {
    AttentionMode.AI_ACTIVE: "Atención automática",
    AttentionMode.HUMAN_PENDING: "Pendiente de asesor",
    AttentionMode.HUMAN_ACTIVE: "Asesor en control",
    AttentionMode.CLOSED: "Cerrada",
}

OPEN_MODES = {
    AttentionMode.AI_ACTIVE,
    AttentionMode.HUMAN_PENDING,
    AttentionMode.HUMAN_ACTIVE,
}

TAKEOVER_FROM = {AttentionMode.AI_ACTIVE, AttentionMode.HUMAN_PENDING}
RESUME_FROM = {AttentionMode.HUMAN_PENDING, AttentionMode.HUMAN_ACTIVE}


def commercial_label(value: str | None) -> str:
    if not value:
        return "Sin clasificar"
    try:
        return COMMERCIAL_LABELS[CommercialState(value)]
    except ValueError:
        return "Sin clasificar"


def attention_label(value: str) -> str:
    try:
        return ATTENTION_LABELS[AttentionMode(value)]
    except ValueError:
        return value
