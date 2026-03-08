import { memo, useMemo } from "react";
import {
  LineChart,
  Line,
  BarChart,
  Bar,
  PieChart,
  Pie,
  Cell,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
} from "recharts";
import type { ChartData, ReportData } from "@/types/ai";

const FALLBACK_COLORS = [
  "#F97316", "#3B82F6", "#22C55E", "#F59E0B", "#EF4444",
  "#8B5CF6", "#14B8A6", "#EC4899",
];

function fmtINR(n: number) {
  if (n >= 100000) return `₹${(n / 100000).toFixed(1)}L`;
  return "₹" + n.toLocaleString("en-IN", { maximumFractionDigits: 0 });
}

function truncLabel(s: string, max = 12) {
  if (!s) return "";
  return s.length > max ? s.slice(0, max - 1) + "…" : s;
}

interface Props {
  chart: ChartData;
  data: ReportData;
}

function InlineChartInner({ chart, data }: Props) {
  // Transform tabular data (columns + rows) into recharts object array
  const chartRows = useMemo(() => {
    return data.rows.map((row) => {
      const obj: Record<string, unknown> = {};
      data.columns.forEach((col, i) => {
        obj[col] = row[i];
      });
      // Truncate long x-axis labels for readability
      if (obj[chart.x_key] && typeof obj[chart.x_key] === "string") {
        obj[`${chart.x_key}_full`] = obj[chart.x_key];
        obj[chart.x_key] = truncLabel(obj[chart.x_key] as string, 15);
      }
      return obj;
    });
  }, [data, chart.x_key]);

  const tooltipFormatter = (value: number | string | undefined, name?: string) => {
    const formatted =
      typeof value === "number"
        ? chart.currency_axis
          ? fmtINR(value)
          : value.toLocaleString("en-IN")
        : value;
    if (name == null) return formatted;
    return [formatted, name];
  };

  const yAxisFormatter = (v: number) => {
    if (!chart.currency_axis) return v.toLocaleString("en-IN");
    if (v >= 100000) return `₹${(v / 100000).toFixed(0)}L`;
    if (v >= 1000) return `₹${(v / 1000).toFixed(0)}K`;
    return `₹${v}`;
  };

  // ─── Line Chart ───────────────────────────────────────────
  if (chart.chart_type === "line") {
    return (
      <ResponsiveContainer width="100%" height={220}>
        <LineChart data={chartRows} margin={{ top: 5, right: 10, left: 0, bottom: 5 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
          <XAxis dataKey={chart.x_key} tick={{ fontSize: 10 }} interval="preserveStartEnd" />
          <YAxis tick={{ fontSize: 10 }} tickFormatter={yAxisFormatter} width={55} />
          <Tooltip formatter={tooltipFormatter} />
          <Legend iconSize={8} wrapperStyle={{ fontSize: 11 }} />
          {chart.series.map((s, i) => (
            <Line
              key={s.data_key}
              type="monotone"
              dataKey={s.data_key}
              name={s.name}
              stroke={s.color || FALLBACK_COLORS[i % FALLBACK_COLORS.length]}
              strokeWidth={2}
              dot={{ r: 2 }}
              activeDot={{ r: 4 }}
            />
          ))}
        </LineChart>
      </ResponsiveContainer>
    );
  }

  // ─── Pie Chart ────────────────────────────────────────────
  if (chart.chart_type === "pie") {
    const pieData = chartRows.map((row, i) => ({
      name: row[chart.x_key] as string,
      value: row[chart.series[0].data_key] as number,
      color: FALLBACK_COLORS[i % FALLBACK_COLORS.length],
    }));

    return (
      <ResponsiveContainer width="100%" height={220}>
        <PieChart>
          <Pie
            data={pieData}
            cx="50%"
            cy="50%"
            innerRadius={50}
            outerRadius={80}
            dataKey="value"
            nameKey="name"
            label={({ name, percent }) => {
              const safeName = typeof name === "string" ? name : name == null ? "" : String(name);
              const safePercent = typeof percent === "number" ? percent : 0;
              return `${truncLabel(safeName, 10)} ${(safePercent * 100).toFixed(0)}%`;
            }}
            labelLine={false}
          >
            {pieData.map((entry, i) => (
              <Cell key={i} fill={entry.color} />
            ))}
          </Pie>
          <Tooltip formatter={tooltipFormatter} />
          <Legend iconSize={8} wrapperStyle={{ fontSize: 11 }} />
        </PieChart>
      </ResponsiveContainer>
    );
  }

  // ─── Bar / Stacked Bar / Grouped Bar ──────────────────────
  const isStacked = chart.chart_type === "stacked_bar";

  return (
    <ResponsiveContainer width="100%" height={220}>
      <BarChart data={chartRows} margin={{ top: 5, right: 10, left: 0, bottom: 5 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
        <XAxis dataKey={chart.x_key} tick={{ fontSize: 10 }} interval={0} angle={-20} textAnchor="end" height={50} />
        <YAxis tick={{ fontSize: 10 }} tickFormatter={yAxisFormatter} width={55} />
        <Tooltip formatter={tooltipFormatter} />
        <Legend iconSize={8} wrapperStyle={{ fontSize: 11 }} />
        {chart.series.map((s, i) => (
          <Bar
            key={s.data_key}
            dataKey={s.data_key}
            name={s.name}
            fill={s.color || FALLBACK_COLORS[i % FALLBACK_COLORS.length]}
            stackId={isStacked ? "stack" : undefined}
            radius={isStacked ? undefined : [2, 2, 0, 0]}
            maxBarSize={40}
          />
        ))}
      </BarChart>
    </ResponsiveContainer>
  );
}

// Memoize to prevent re-renders when sibling messages update
const InlineChart = memo(InlineChartInner);
export default InlineChart;
