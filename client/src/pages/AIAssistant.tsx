import { useState, useEffect, useCallback } from "react";
import api from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import {
  Bot,
  Plus,
  Trash2,
  Send,
  Loader2,
  Download,
  User,
  MessageSquare,
  Sparkles,
  Globe,
  ChevronDown,
  ChevronUp,
  BarChart3,
} from "lucide-react";
import { cn } from "@/lib/utils";
import InlineChart from "@/components/chat/InlineChart";
import type {
  ChatMessage,
  ChatSession,
  ChatResponse,
  ReportData,
} from "@/types/ai";

// ─── Inline sub-components (self-contained page) ────────────────────

function fmtINR(n: number) {
  return "₹" + n.toLocaleString("en-IN", { maximumFractionDigits: 0 });
}

function isCurrencyCol(col: string) {
  return /price|revenue|amount|gmv|cost/i.test(col);
}

function DataTable({
  data,
  onExport,
  collapsed,
}: {
  data: ReportData;
  onExport?: () => void;
  collapsed?: boolean;
}) {
  const [open, setOpen] = useState(!collapsed);

  return (
    <div className="mt-2 rounded-lg border bg-white">
      <div className="flex items-center justify-between border-b px-4 py-2">
        <button
          className="flex items-center gap-1.5 text-xs text-muted-foreground hover:text-gray-700"
          onClick={() => setOpen((v) => !v)}
        >
          {open ? <ChevronUp className="h-3 w-3" /> : <ChevronDown className="h-3 w-3" />}
          {data.report_type.replace(/_/g, " ")} &middot; {data.rows.length} rows
        </button>
        {onExport && (
          <Button variant="ghost" size="sm" onClick={onExport} className="h-7 text-xs">
            <Download className="mr-1 h-3 w-3" />
            CSV
          </Button>
        )}
      </div>
      {open && (
        <div className="overflow-x-auto max-h-64">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b bg-muted/50">
                {data.columns.map((col) => (
                  <th
                    key={col}
                    className="px-4 py-2 text-left text-xs font-medium text-muted-foreground whitespace-nowrap"
                  >
                    {col.replace(/_/g, " ")}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {data.rows.map((row, i) => (
                <tr key={i} className="border-b last:border-0 hover:bg-muted/30">
                  {row.map((cell, j) => (
                    <td key={j} className="px-4 py-2 whitespace-nowrap">
                      {typeof cell === "number" && isCurrencyCol(data.columns[j])
                        ? fmtINR(cell)
                        : typeof cell === "boolean"
                        ? cell ? "Yes" : "No"
                        : cell === null
                        ? "—"
                        : Array.isArray(cell)
                        ? cell.join(", ")
                        : typeof cell === "object"
                        ? JSON.stringify(cell)
                        : String(cell)}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

function WebSources({ sources }: { sources: { title: string; url: string }[] }) {
  if (!sources.length) return null;
  return (
    <div className="mt-2 flex flex-wrap gap-1.5">
      <Globe className="h-3.5 w-3.5 text-blue-400 mt-0.5" />
      {sources.map((src, i) => (
        <a
          key={i}
          href={src.url}
          target="_blank"
          rel="noopener noreferrer"
          className="inline-flex items-center rounded-md border bg-blue-50 px-2 py-0.5 text-xs text-blue-600 hover:bg-blue-100 transition-colors"
        >
          [{i + 1}] {src.title.length > 40 ? src.title.slice(0, 37) + "…" : src.title}
        </a>
      ))}
    </div>
  );
}

function MessageBubble({
  message,
  onExport,
}: {
  message: ChatMessage;
  onExport?: (messageId: number) => void;
}) {
  const isUser = message.role === "user";
  const hasChart = !!message.chart_data && !!message.report_data;

  return (
    <div className={cn("flex gap-3 px-4", isUser ? "flex-row-reverse" : "flex-row")}>
      <div
        className={cn(
          "flex h-8 w-8 shrink-0 items-center justify-center rounded-full",
          isUser ? "bg-primary/10 text-primary" : "bg-gray-100 text-gray-600"
        )}
      >
        {isUser ? <User className="h-4 w-4" /> : <Bot className="h-4 w-4" />}
      </div>
      <div className={cn("max-w-[85%] space-y-1", isUser ? "text-right" : "text-left")}>
        <div
          className={cn(
            "inline-block rounded-2xl px-4 py-2.5 text-sm leading-relaxed",
            isUser
              ? "bg-primary text-white rounded-br-md"
              : "bg-white border rounded-bl-md text-gray-800"
          )}
        >
          {message.content.split("\n").map((line, i) => (
            <span key={i}>
              {line
                .replace(/\*\*(.*?)\*\*/g, "⟨b⟩$1⟨/b⟩")
                .split(/⟨\/?b⟩/)
                .map((part, j) =>
                  j % 2 === 1 ? (
                    <strong key={j}>{part}</strong>
                  ) : (
                    <span key={j}>{part}</span>
                  )
                )}
              {i < message.content.split("\n").length - 1 && <br />}
            </span>
          ))}
        </div>

        {/* Chart — rendered above the data table */}
        {hasChart && (
          <div className="mt-2 rounded-lg border bg-white p-3">
            <div className="flex items-center gap-1.5 mb-2">
              <BarChart3 className="h-3.5 w-3.5 text-primary" />
              <span className="text-xs font-medium text-muted-foreground">
                {message.chart_data!.title}
              </span>
            </div>
            <InlineChart chart={message.chart_data!} data={message.report_data!} />
          </div>
        )}

        {/* Data table — collapsed by default when chart is shown */}
        {message.report_data && (
          <DataTable
            data={message.report_data}
            onExport={onExport ? () => onExport(message.id) : undefined}
            collapsed={hasChart}
          />
        )}

        {/* Web source citations */}
        {message.web_sources && message.web_sources.length > 0 && (
          <WebSources sources={message.web_sources} />
        )}
      </div>
    </div>
  );
}

// ─── Suggested Questions ─────────────────────────────────────────────

const DEFAULT_SUGGESTIONS = [
  "What are my top selling products?",
  "Show sales trend for last 30 days",
  "Which products are at stockout risk?",
  "How is my buy box performance?",
  "What are current e-commerce trends in India?",
  "What's my revenue this month?",
];

// ─── Main Page ───────────────────────────────────────────────────────

export function AIAssistantPage() {
  const [sessions, setSessions] = useState<ChatSession[]>([]);
  const [activeSessionId, setActiveSessionId] = useState<number | null>(null);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [suggestions, setSuggestions] = useState<string[]>(DEFAULT_SUGGESTIONS);
  const [sidebarOpen, setSidebarOpen] = useState(true);

  // Fetch sessions on mount
  useEffect(() => {
    api.get("/ai/sessions").then(({ data }) => setSessions(data)).catch(() => {});
  }, []);

  // Fetch messages when session changes
  useEffect(() => {
    if (activeSessionId) {
      api
        .get(`/ai/sessions/${activeSessionId}/messages`)
        .then(({ data }) => setMessages(data))
        .catch(() => setMessages([]));
    } else {
      setMessages([]);
    }
  }, [activeSessionId]);

  // Auto-scroll
  useEffect(() => {
    const el = document.getElementById("chat-scroll-anchor");
    el?.scrollIntoView({ behavior: "smooth" });
  }, [messages, loading]);

  const refreshSessions = useCallback(() => {
    api.get("/ai/sessions").then(({ data }) => setSessions(data)).catch(() => {});
  }, []);

  const handleSend = async (text?: string) => {
    const msg = (text || input).trim();
    if (!msg || loading) return;
    setInput("");
    setLoading(true);

    // Optimistically add user message
    const tempUserMsg: ChatMessage = {
      id: Date.now(),
      role: "user",
      content: msg,
      report_data: null,
      chart_data: null,
      web_sources: [],
      created_at: new Date().toISOString(),
    };
    setMessages((prev) => [...prev, tempUserMsg]);

    try {
      const { data } = await api.post<ChatResponse>("/ai/chat", {
        session_id: activeSessionId,
        message: msg,
      });

      // Update session ID if new
      if (!activeSessionId || data.session_id !== activeSessionId) {
        setActiveSessionId(data.session_id);
      }

      // Add assistant response
      const assistantMsg: ChatMessage = {
        id: data.message_id || Date.now() + 1,
        role: "assistant",
        content: data.content,
        report_data: data.report_data,
        chart_data: data.chart_data,
        web_sources: data.web_sources || [],
        created_at: new Date().toISOString(),
      };
      setMessages((prev) => [...prev, assistantMsg]);

      if (data.suggested_questions?.length) {
        setSuggestions(data.suggested_questions);
      }

      refreshSessions();
    } catch (err: any) {
      const errorMsg: ChatMessage = {
        id: Date.now() + 1,
        role: "assistant",
        content: err.response?.data?.detail || "Something went wrong. Please try again.",
        report_data: null,
        chart_data: null,
        web_sources: [],
        created_at: new Date().toISOString(),
      };
      setMessages((prev) => [...prev, errorMsg]);
    } finally {
      setLoading(false);
    }
  };

  const handleNewChat = () => {
    setActiveSessionId(null);
    setMessages([]);
    setSuggestions(DEFAULT_SUGGESTIONS);
  };

  const handleDeleteSession = async (id: number) => {
    try {
      await api.delete(`/ai/sessions/${id}`);
      setSessions((prev) => prev.filter((s) => s.id !== id));
      if (activeSessionId === id) {
        handleNewChat();
      }
    } catch {}
  };

  const handleExport = async (messageId: number) => {
    try {
      const { data } = await api.post("/ai/export", { message_id: messageId });
      const blob = new Blob([data.csv_data], { type: "text/csv" });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = data.filename;
      a.click();
      URL.revokeObjectURL(url);
    } catch {}
  };

  return (
    <div className="flex h-[calc(100vh-8rem)] gap-0 overflow-hidden rounded-xl border bg-white shadow-sm">
      {/* Sidebar */}
      {sidebarOpen && (
        <div className="flex w-72 flex-col border-r bg-gray-50">
          <div className="flex items-center justify-between border-b p-4">
            <h3 className="text-sm font-semibold">Conversations</h3>
            <Button variant="ghost" size="sm" onClick={handleNewChat} className="h-8">
              <Plus className="mr-1 h-3.5 w-3.5" />
              New
            </Button>
          </div>
          <div className="flex-1 overflow-y-auto p-2">
            {sessions.length === 0 ? (
              <p className="p-4 text-center text-xs text-muted-foreground">
                No conversations yet
              </p>
            ) : (
              sessions.map((s) => (
                <div
                  key={s.id}
                  className={cn(
                    "group flex items-center justify-between rounded-lg px-3 py-2.5 cursor-pointer transition-colors mb-1",
                    activeSessionId === s.id
                      ? "bg-primary/5 border border-primary/20"
                      : "hover:bg-gray-100"
                  )}
                  onClick={() => setActiveSessionId(s.id)}
                >
                  <div className="min-w-0 flex-1">
                    <div className="truncate text-sm font-medium">
                      {s.title || "New Chat"}
                    </div>
                    <div className="text-xs text-muted-foreground">
                      {s.message_count} messages &middot;{" "}
                      {new Date(s.updated_at).toLocaleDateString("en-IN", {
                        day: "numeric",
                        month: "short",
                      })}
                    </div>
                  </div>
                  <button
                    className="ml-2 hidden rounded p-1 text-muted-foreground hover:bg-red-50 hover:text-red-500 group-hover:block"
                    onClick={(e) => {
                      e.stopPropagation();
                      handleDeleteSession(s.id);
                    }}
                  >
                    <Trash2 className="h-3.5 w-3.5" />
                  </button>
                </div>
              ))
            )}
          </div>
        </div>
      )}

      {/* Main Chat Area */}
      <div className="flex flex-1 flex-col">
        {/* Chat Header */}
        <div className="flex items-center gap-3 border-b px-6 py-3">
          <button
            onClick={() => setSidebarOpen((v) => !v)}
            className="rounded p-1 hover:bg-gray-100"
          >
            <MessageSquare className="h-4 w-4 text-muted-foreground" />
          </button>
          <div className="flex items-center gap-2">
            <div className="flex h-8 w-8 items-center justify-center rounded-full bg-primary/10">
              <Sparkles className="h-4 w-4 text-primary" />
            </div>
            <div>
              <h3 className="text-sm font-semibold">RetailSutra AI</h3>
              <p className="text-xs text-muted-foreground">
                Ask about sales, inventory, pricing, reviews &mdash; or search the web
              </p>
            </div>
          </div>
        </div>

        {/* Messages */}
        <div className="flex-1 overflow-y-auto py-6 space-y-6">
          {messages.length === 0 && !loading ? (
            <div className="flex flex-col items-center justify-center h-full text-center px-8">
              <div className="flex h-16 w-16 items-center justify-center rounded-2xl bg-primary/5 mb-4">
                <Bot className="h-8 w-8 text-primary" />
              </div>
              <h3 className="text-lg font-semibold mb-2">RetailSutra AI Assistant</h3>
              <p className="text-sm text-muted-foreground mb-6 max-w-md">
                Ask me anything about your business — sales trends, inventory health,
                pricing analysis, customer sentiment. I can also search the web for market trends.
              </p>
              <div className="grid grid-cols-2 gap-2 max-w-lg">
                {DEFAULT_SUGGESTIONS.map((q) => (
                  <button
                    key={q}
                    className="rounded-lg border px-3 py-2 text-left text-sm hover:bg-primary/5 hover:border-primary/20 transition-colors"
                    onClick={() => handleSend(q)}
                  >
                    {q}
                  </button>
                ))}
              </div>
            </div>
          ) : (
            <>
              {messages.map((msg) => (
                <MessageBubble
                  key={msg.id}
                  message={msg}
                  onExport={msg.report_data ? handleExport : undefined}
                />
              ))}
              {loading && (
                <div className="flex gap-3 px-4">
                  <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-gray-100">
                    <Bot className="h-4 w-4 text-gray-600" />
                  </div>
                  <div className="flex items-center gap-2 rounded-2xl border bg-white px-4 py-2.5 rounded-bl-md">
                    <Loader2 className="h-4 w-4 animate-spin text-primary" />
                    <span className="text-sm text-muted-foreground">Thinking...</span>
                  </div>
                </div>
              )}
              <div id="chat-scroll-anchor" />
            </>
          )}
        </div>

        {/* Suggestion Chips (when there are messages) */}
        {messages.length > 0 && suggestions.length > 0 && !loading && (
          <div className="flex gap-2 overflow-x-auto px-6 pb-2">
            {suggestions.map((q) => (
              <Badge
                key={q}
                variant="secondary"
                className="cursor-pointer whitespace-nowrap hover:bg-primary/5 hover:text-primary"
                onClick={() => handleSend(q)}
              >
                {q}
              </Badge>
            ))}
          </div>
        )}

        {/* Input */}
        <div className="border-t bg-gray-50 p-4">
          <div className="flex gap-2">
            <input
              type="text"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter" && !e.shiftKey) {
                  e.preventDefault();
                  handleSend();
                }
              }}
              placeholder="Ask about your business or search the web..."
              disabled={loading}
              className="flex-1 rounded-lg border bg-white px-4 py-2.5 text-sm focus:border-primary/40 focus:outline-none focus:ring-2 focus:ring-primary/10 disabled:opacity-50"
            />
            <Button
              onClick={() => handleSend()}
              disabled={loading || !input.trim()}
              className="bg-primary hover:bg-primary/90"
            >
              {loading ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                <Send className="h-4 w-4" />
              )}
            </Button>
          </div>
        </div>
      </div>
    </div>
  );
}
