import { useState } from "react";
import { Plus, Trash2, MessageSquare } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Separator } from "@/components/ui/separator";
import { cn } from "@/lib/utils";
import type { ChatSession } from "@/types/ai";

interface ChatSidebarProps {
  sessions: ChatSession[];
  activeSessionId: number | null;
  onSelectSession: (id: number) => void;
  onNewChat: () => void;
  onDeleteSession: (id: number) => void;
}

function formatSessionDate(dateStr: string): string {
  const date = new Date(dateStr);
  const now = new Date();
  const diffMs = now.getTime() - date.getTime();
  const diffDays = Math.floor(diffMs / (1000 * 60 * 60 * 24));

  if (diffDays === 0) return "Today";
  if (diffDays === 1) return "Yesterday";
  if (diffDays < 7) return `${diffDays}d ago`;
  return date.toLocaleDateString("en-IN", {
    day: "numeric",
    month: "short",
  });
}

export function ChatSidebar({
  sessions,
  activeSessionId,
  onSelectSession,
  onNewChat,
  onDeleteSession,
}: ChatSidebarProps) {
  const [hoveredId, setHoveredId] = useState<number | null>(null);

  return (
    <div className="flex h-full w-full flex-col bg-muted/30">
      {/* Header + New Chat */}
      <div className="p-3">
        <Button
          onClick={onNewChat}
          className="w-full gap-2 bg-orange-500 hover:bg-orange-600"
          size="sm"
        >
          <Plus className="size-4" />
          New Chat
        </Button>
      </div>

      <Separator />

      {/* Session list */}
      <div className="flex-1 overflow-y-auto p-2">
        {sessions.length === 0 ? (
          <div className="flex flex-col items-center gap-2 py-8 text-center">
            <MessageSquare className="size-8 text-muted-foreground/50" />
            <p className="text-xs text-muted-foreground">No conversations yet</p>
          </div>
        ) : (
          <div className="flex flex-col gap-0.5">
            {sessions.map((session) => {
              const isActive = session.id === activeSessionId;
              const isHovered = session.id === hoveredId;

              return (
                <button
                  key={session.id}
                  onClick={() => onSelectSession(session.id)}
                  onMouseEnter={() => setHoveredId(session.id)}
                  onMouseLeave={() => setHoveredId(null)}
                  className={cn(
                    "group relative flex w-full items-start gap-2 rounded-lg px-3 py-2.5 text-left text-sm transition-colors",
                    isActive
                      ? "bg-orange-50 text-orange-900 dark:bg-orange-950/30 dark:text-orange-100"
                      : "text-foreground hover:bg-muted"
                  )}
                >
                  <MessageSquare
                    className={cn(
                      "mt-0.5 size-4 shrink-0",
                      isActive
                        ? "text-orange-500"
                        : "text-muted-foreground"
                    )}
                  />
                  <div className="flex min-w-0 flex-1 flex-col gap-0.5">
                    <span className="truncate text-sm font-medium">
                      {session.title || "New conversation"}
                    </span>
                    <span className="text-xs text-muted-foreground">
                      {formatSessionDate(session.updated_at)} &middot;{" "}
                      {session.message_count}{" "}
                      {session.message_count === 1 ? "message" : "messages"}
                    </span>
                  </div>

                  {/* Delete button - shown on hover */}
                  {(isHovered || isActive) && (
                    <button
                      onClick={(e) => {
                        e.stopPropagation();
                        onDeleteSession(session.id);
                      }}
                      className="mt-0.5 shrink-0 rounded p-1 text-muted-foreground transition-colors hover:bg-destructive/10 hover:text-destructive"
                      aria-label="Delete conversation"
                    >
                      <Trash2 className="size-3.5" />
                    </button>
                  )}
                </button>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}
