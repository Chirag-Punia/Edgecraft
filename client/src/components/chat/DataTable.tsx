import { Download } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";
import type { ReportData } from "@/types/ai";

interface DataTableProps {
  data: ReportData;
  onExport?: () => void;
}

const CURRENCY_KEYWORDS = ["price", "revenue", "amount", "gmv", "cost", "margin", "value", "total"];

function isCurrencyColumn(columnName: string): boolean {
  const lower = columnName.toLowerCase();
  return CURRENCY_KEYWORDS.some((kw) => lower.includes(kw));
}

function formatCellValue(
  value: string | number | boolean | null,
  columnName: string
): string {
  if (value === null || value === undefined) return "-";
  if (typeof value === "boolean") return value ? "Yes" : "No";

  if (typeof value === "number") {
    if (isCurrencyColumn(columnName)) {
      return new Intl.NumberFormat("en-IN", {
        style: "currency",
        currency: "INR",
        minimumFractionDigits: 0,
        maximumFractionDigits: 2,
      }).format(value);
    }
    return new Intl.NumberFormat("en-IN").format(value);
  }

  return String(value);
}

export function DataTable({ data, onExport }: DataTableProps) {
  const { columns, rows, report_type, time_range } = data;

  return (
    <div className="w-full overflow-hidden rounded-lg border bg-card text-card-foreground shadow-sm">
      {/* Header bar */}
      <div className="flex items-center justify-between gap-2 border-b px-4 py-2.5">
        <div className="flex items-center gap-2">
          <Badge variant="secondary" className="text-xs capitalize">
            {report_type.replace(/_/g, " ")}
          </Badge>
          <span className="text-xs text-muted-foreground">{time_range}</span>
        </div>
        {onExport && (
          <Button variant="ghost" size="xs" onClick={onExport}>
            <Download className="size-3" />
            Export CSV
          </Button>
        )}
      </div>

      {/* Table */}
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b bg-muted/50">
              {columns.map((col, i) => (
                <th
                  key={i}
                  className={cn(
                    "whitespace-nowrap px-4 py-2.5 text-left text-xs font-medium text-muted-foreground",
                    typeof rows[0]?.[i] === "number" && "text-right"
                  )}
                >
                  {col}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.map((row, rowIndex) => (
              <tr
                key={rowIndex}
                className={cn(
                  "border-b transition-colors last:border-b-0 hover:bg-muted/30",
                  rowIndex % 2 === 0 ? "bg-transparent" : "bg-muted/10"
                )}
              >
                {row.map((cell, cellIndex) => (
                  <td
                    key={cellIndex}
                    className={cn(
                      "whitespace-nowrap px-4 py-2",
                      typeof cell === "number" && "text-right font-mono text-xs"
                    )}
                  >
                    {formatCellValue(cell, columns[cellIndex])}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Footer with row count */}
      <div className="border-t px-4 py-2">
        <span className="text-xs text-muted-foreground">
          {rows.length} {rows.length === 1 ? "row" : "rows"}
        </span>
      </div>
    </div>
  );
}
