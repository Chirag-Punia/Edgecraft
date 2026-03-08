import { useEffect, useRef } from "react";
import { Bot, MessageSquareText } from "lucide-react";
import { cn } from "@/lib/utils";
import type { ChatMessage as ChatMessageType } from "@/types/ai";
import { ChatMessage } from "./ChatMessage";

interface ChatWindowProps {
  messages: ChatMessageType[];
  loading?: boolean;
}

export function ChatWindow({ messages, loading }: ChatWindowProps) {
  const bottomRef = useRef<HTMLDivElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);

  // Auto-scroll to bottom on new messages or loading state change
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, loading]);

  // Empty state
  if (messages.length === 0 && !loading) {
    return (
      <div className="flex h-full flex-col items-center justify-center gap-4 px-6 text-center">
        <div className="flex size-16 items-center justify-center rounded-2xl bg-orange-50 text-orange-500 dark:bg-orange-950/30">
          <MessageSquareText className="size-8" />
        </div>
        <div className="flex flex-col gap-1.5">
          <h3 className="text-lg font-semibold text-foreground">
            Start a conversation with your AI assistant
          </h3>
          <p className="max-w-sm text-sm text-muted-foreground">
            Ask about your sales, inventory, pricing, customer feedback, or
            anything else about your business.
          </p>
        </div>
      </div>
    );
  }

  return (
    <div
      ref={containerRef}
      className="flex h-full flex-col gap-6 overflow-y-auto px-4 py-6"
    >
      {messages.map((msg) => (
        <ChatMessage key={msg.id} message={msg} />
      ))}

      {/* Typing indicator */}
      {loading && (
        <div className="flex items-start gap-3">
          <div className="flex size-8 shrink-0 items-center justify-center rounded-full bg-muted text-muted-foreground">
            <Bot className="size-4" />
          </div>
          <div className="rounded-2xl rounded-tl-sm bg-muted px-4 py-3">
            <div className="flex items-center gap-1.5">
              <span
                className={cn(
                  "inline-block size-2 rounded-full bg-muted-foreground/60",
                  "animate-bounce [animation-delay:0ms]"
                )}
              />
              <span
                className={cn(
                  "inline-block size-2 rounded-full bg-muted-foreground/60",
                  "animate-bounce [animation-delay:150ms]"
                )}
              />
              <span
                className={cn(
                  "inline-block size-2 rounded-full bg-muted-foreground/60",
                  "animate-bounce [animation-delay:300ms]"
                )}
              />
            </div>
          </div>
        </div>
      )}

      <div ref={bottomRef} />
    </div>
  );
}
