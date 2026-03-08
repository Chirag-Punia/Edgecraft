import { User, Bot } from "lucide-react";
import { cn } from "@/lib/utils";
import type { ChatMessage as ChatMessageType } from "@/types/ai";
import { DataTable } from "./DataTable";

interface ChatMessageProps {
  message: ChatMessageType;
}

function formatContent(content: string): React.ReactNode[] {
  const lines = content.split("\n");
  const elements: React.ReactNode[] = [];

  lines.forEach((line, lineIndex) => {
    if (lineIndex > 0) {
      elements.push(<br key={`br-${lineIndex}`} />);
    }

    const trimmed = line.trim();

    // Bullet points
    if (trimmed.startsWith("- ") || trimmed.startsWith("* ")) {
      const bulletContent = trimmed.slice(2);
      elements.push(
        <span key={`line-${lineIndex}`} className="flex items-start gap-1.5">
          <span className="mt-1.5 inline-block size-1.5 shrink-0 rounded-full bg-current opacity-60" />
          <span>{formatInline(bulletContent)}</span>
        </span>
      );
      return;
    }

    elements.push(
      <span key={`line-${lineIndex}`}>{formatInline(line)}</span>
    );
  });

  return elements;
}

function formatInline(text: string): React.ReactNode[] {
  // Handle **bold** patterns
  const parts: React.ReactNode[] = [];
  const regex = /\*\*(.+?)\*\*/g;
  let lastIndex = 0;
  let match: RegExpExecArray | null;

  while ((match = regex.exec(text)) !== null) {
    if (match.index > lastIndex) {
      parts.push(text.slice(lastIndex, match.index));
    }
    parts.push(
      <strong key={`bold-${match.index}`} className="font-semibold">
        {match[1]}
      </strong>
    );
    lastIndex = regex.lastIndex;
  }

  if (lastIndex < text.length) {
    parts.push(text.slice(lastIndex));
  }

  return parts.length > 0 ? parts : [text];
}

export function ChatMessage({ message }: ChatMessageProps) {
  const isUser = message.role === "user";

  return (
    <div
      className={cn(
        "flex w-full gap-3",
        isUser ? "flex-row-reverse" : "flex-row"
      )}
    >
      {/* Avatar */}
      <div
        className={cn(
          "flex size-8 shrink-0 items-center justify-center rounded-full",
          isUser
            ? "bg-orange-500 text-white"
            : "bg-muted text-muted-foreground"
        )}
      >
        {isUser ? <User className="size-4" /> : <Bot className="size-4" />}
      </div>

      {/* Message bubble + optional table */}
      <div
        className={cn(
          "flex max-w-[75%] flex-col gap-2",
          isUser ? "items-end" : "items-start"
        )}
      >
        <div
          className={cn(
            "rounded-2xl px-4 py-2.5 text-sm leading-relaxed",
            isUser
              ? "rounded-tr-sm bg-orange-500 text-white"
              : "rounded-tl-sm bg-muted text-foreground"
          )}
        >
          {formatContent(message.content)}
        </div>

        {message.report_data && (
          <div className="w-full">
            <DataTable data={message.report_data} />
          </div>
        )}

        <span className="px-1 text-xs text-muted-foreground">
          {new Date(message.created_at).toLocaleTimeString([], {
            hour: "2-digit",
            minute: "2-digit",
          })}
        </span>
      </div>
    </div>
  );
}
