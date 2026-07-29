from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1)
    thread_id: str = Field(..., min_length=1)
    history: list[dict[str, str]] = Field(default_factory=list)  # ignorado; memoria vía checkpointer


class ChatResponse(BaseModel):
    reply: str
    thread_id: str


class ChatHistoryResponse(BaseModel):
    thread_id: str
    messages: list[dict[str, str]] = Field(default_factory=list)


class ClearChatRequest(BaseModel):
    thread_id: str = Field(..., min_length=1)


class DocumentInfo(BaseModel):
    id: str
    title: str
    tags: list[str] = Field(default_factory=list)
    source: str = ""
    created_at: str = ""


class UploadResponse(BaseModel):
    id: str
    title: str
    message: str
