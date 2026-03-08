import { Info } from "lucide-react";

interface InfoTipProps {
  text: string;
}

export function InfoTip({ text }: InfoTipProps) {
  return (
    <span className="group relative inline-flex">
      <Info className="h-3.5 w-3.5 text-muted-foreground/60 cursor-help" />
      <span className="pointer-events-none absolute bottom-full left-1/2 z-50 mb-2 -translate-x-1/2 whitespace-normal rounded-md bg-popover px-3 py-2 text-xs text-popover-foreground shadow-md border opacity-0 transition-opacity group-hover:opacity-100 w-56 text-center leading-relaxed">
        {text}
      </span>
    </span>
  );
}
