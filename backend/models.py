"""Pydantic models + Mongo helpers for Consenso Plus."""
from pydantic import BaseModel, Field, EmailStr, ConfigDict
from typing import List, Optional, Literal, Dict, Any
from datetime import datetime, timezone
import uuid


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def new_id() -> str:
    return str(uuid.uuid4())


# ---------- Auth / Tenant ----------
class Tenant(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=new_id)
    name: str
    slug: str
    plan: str = "pro"
    default_language: str = "pt"
    created_at: str = Field(default_factory=now_iso)


class User(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=new_id)
    tenant_id: str
    email: EmailStr
    name: str
    role: Literal["owner", "admin", "agent", "platform_admin"] = "owner"
    created_at: str = Field(default_factory=now_iso)


class RegisterInput(BaseModel):
    company_name: str
    email: EmailStr
    password: str
    name: str


class LoginInput(BaseModel):
    email: EmailStr
    password: str


class AuthResponse(BaseModel):
    token: str
    user: User
    tenant: Tenant


# ---------- Agents ----------
class AgentTool(BaseModel):
    key: str
    enabled: bool = True


class Agent(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=new_id)
    tenant_id: str
    name: str
    avatar_url: str = ""
    welcome_message: str = "Olá! Como posso ajudar?"
    icebreakers: List[str] = Field(default_factory=list)
    tone: str = "profissional"
    goal: str = "Ajudar clientes"
    system_prompt: str = "És um assistente útil."
    rules: str = ""
    api_provider: Literal["emergent", "openai", "anthropic", "gemini"] = "emergent"
    api_key: str = ""
    model_provider: Literal["openai", "anthropic", "gemini", "auto"] = "auto"
    model_name: str = "gpt-5.1"
    tools: List[AgentTool] = Field(default_factory=list)
    knowledge: str = ""
    data_source_ids: List[str] = Field(default_factory=list)
    default_language: str = "pt"
    notify_email: str = ""
    channels: Dict[str, Dict[str, Any]] = Field(default_factory=dict)
    active: bool = True
    created_at: str = Field(default_factory=now_iso)


class AgentInput(BaseModel):
    name: str
    avatar_url: str = ""
    welcome_message: str = "Olá! Como posso ajudar?"
    icebreakers: List[str] = Field(default_factory=list)
    tone: str = "profissional"
    goal: str = "Ajudar clientes"
    system_prompt: str = "És um assistente útil."
    rules: str = ""
    api_provider: str = "emergent"
    api_key: str = ""
    model_provider: str = "auto"
    model_name: str = "gpt-5.1"
    tools: List[AgentTool] = Field(default_factory=list)
    knowledge: str = ""
    data_source_ids: List[str] = Field(default_factory=list)
    default_language: str = "pt"
    notify_email: str = ""
    channels: Dict[str, Dict[str, Any]] = Field(default_factory=dict)
    active: bool = True


# ---------- Data Sources ----------
class DataSource(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=new_id)
    tenant_id: str
    kind: Literal["url", "text", "file"]
    name: str
    url: Optional[str] = None
    status: Literal["pending", "indexed", "error"] = "pending"
    chunks: int = 0
    items: int = 0
    last_indexed_at: Optional[str] = None
    error: Optional[str] = None
    created_at: str = Field(default_factory=now_iso)


class DataSourceURLInput(BaseModel):
    name: str
    url: str


class DataSourceTextInput(BaseModel):
    name: str
    text: str


# ---------- Integrations ----------
class Integration(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=new_id)
    tenant_id: str
    kind: str
    category: Literal["channel", "crm", "email"]
    name: str
    status: Literal["connected", "disconnected", "error"] = "disconnected"
    config: Dict[str, Any] = Field(default_factory=dict)
    created_at: str = Field(default_factory=now_iso)


# ---------- Conversations / Messages ----------
class Conversation(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=new_id)
    tenant_id: str
    channel: str
    external_user_id: str
    contact_name: str
    contact_avatar: Optional[str] = None
    status: Literal["open", "ai", "human", "closed"] = "ai"
    assigned_to: Optional[str] = None
    agent_id: Optional[str] = None
    tags: List[str] = Field(default_factory=list)
    language: Optional[str] = None
    last_message: str = ""
    last_message_at: str = Field(default_factory=now_iso)
    unread: int = 0
    intent: Optional[Dict[str, Any]] = None
    structure: Optional[Dict[str, Any]] = None
    created_at: str = Field(default_factory=now_iso)


class Message(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=new_id)
    tenant_id: str
    conversation_id: str
    sender: Literal["user", "ai", "human"]
    sender_name: str
    text: str
    cards: List[Dict[str, Any]] = Field(default_factory=list)
    meta: Dict[str, Any] = Field(default_factory=dict)
    created_at: str = Field(default_factory=now_iso)


class InboundMessage(BaseModel):
    channel: str = "webchat"
    external_user_id: str
    contact_name: str = "Visitante Web"
    text: str
    tenant_id: Optional[str] = None


class SendMessageInput(BaseModel):
    text: str


# ---------- Leads ----------
class Lead(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=new_id)
    tenant_id: str
    name: str
    email: Optional[str] = None
    phone: Optional[str] = None
    company: Optional[str] = None
    source: str = "webchat"
    stage: Literal["new", "contacted", "qualified", "won", "lost"] = "new"
    score: int = 0
    tags: List[str] = Field(default_factory=list)
    notes: str = ""
    conversation_id: Optional[str] = None
    crm_synced: bool = False
    created_at: str = Field(default_factory=now_iso)


class LeadInput(BaseModel):
    name: str
    email: Optional[str] = None
    phone: Optional[str] = None
    company: Optional[str] = None
    source: str = "manual"
    stage: str = "new"
    score: int = 0
    tags: List[str] = Field(default_factory=list)
    notes: str = ""


# ---------- Tickets ----------
class Ticket(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=new_id)
    tenant_id: str
    subject: str
    description: str = ""
    priority: Literal["low", "medium", "high", "urgent"] = "medium"
    status: Literal["open", "in_progress", "waiting", "resolved", "closed"] = "open"
    assigned_to: Optional[str] = None
    conversation_id: Optional[str] = None
    created_at: str = Field(default_factory=now_iso)


class TicketInput(BaseModel):
    subject: str
    description: str = ""
    priority: str = "medium"
    status: str = "open"
    assigned_to: Optional[str] = None
    conversation_id: Optional[str] = None


# ---------- Team ----------
class TeamInvite(BaseModel):
    email: EmailStr
    name: str
    role: Literal["admin", "agent"] = "agent"
    password: str = "changeme123"
