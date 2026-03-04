import { Card } from "@/components/ui/card";
import { cn } from "@/lib/utils";
import type { KPIData } from "@/types";
import type { LucideIcon } from "lucide-react";

interface KPICardProps extends KPIData {
  icon: LucideIcon;
}

export function KPICard({ title, value, change, change_type, icon: Icon }: KPICardProps) {
  return (
    <Card className="p-4">
      <div className="flex items-center justify-between mb-2">
        <span className="text-sm text-muted-foreground">{title}</span>
        <Icon className="h-4 w-4 text-muted-foreground" />
      </div>
      <div className="text-2xl font-bold">{value}</div>
      <p
        className={cn(
          "mt-1 text-xs",
          change_type === "positive" && "text-green-600",
          change_type === "negative" && "text-red-600",
          change_type === "neutral" && "text-muted-foreground"
        )}
      >
        {change}
      </p>
    </Card>
  );
}
