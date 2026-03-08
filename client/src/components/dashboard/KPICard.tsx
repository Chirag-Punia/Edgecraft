import { Card } from "@/components/ui/card";
import { cn } from "@/lib/utils";
import { InfoTip } from "@/components/dashboard/InfoTip";
import type { KPIData } from "@/types";
import type { LucideIcon } from "lucide-react";
import { TrendingUp, TrendingDown } from "lucide-react";

interface KPICardProps extends KPIData {
  icon: LucideIcon;
  info?: string;
}

export function KPICard({ title, value, change, change_type, icon: Icon, info }: KPICardProps) {
  return (
    <Card className="p-5 hover:shadow-md transition-all duration-200">
      <div className="flex items-start justify-between mb-3">
        <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-primary/10">
          <Icon className="h-5 w-5 text-primary" />
        </div>
        {info && <InfoTip text={info} />}
      </div>
      <div className="text-xs font-medium text-muted-foreground uppercase tracking-wider mb-1">
        {title}
      </div>
      <div className="text-2xl font-bold tracking-tight">{value}</div>
      <div
        className={cn(
          "mt-2 text-xs flex items-center gap-1",
          change_type === "positive" && "text-green-600",
          change_type === "negative" && "text-red-600",
          change_type === "neutral" && "text-muted-foreground"
        )}
      >
        {change_type === "positive" && <TrendingUp className="h-3.5 w-3.5" />}
        {change_type === "negative" && <TrendingDown className="h-3.5 w-3.5" />}
        {change}
      </div>
    </Card>
  );
}
