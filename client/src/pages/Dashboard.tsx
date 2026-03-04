import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { KPICard } from "@/components/dashboard/KPICard";
import {
  IndianRupee,
  TrendingUp,
  ShoppingCart,
  Package,
  RotateCcw,
  AlertTriangle,
  AlertCircle,
} from "lucide-react";
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  PieChart,
  Pie,
  Cell,
  Legend,
} from "recharts";

// Placeholder KPI data matching mockup 6
const KPI_DATA = [
  { title: "Today's GMV", value: "\u20B91,24,560", change: "+12.5% from yesterday", change_type: "positive" as const, icon: IndianRupee },
  { title: "Net Sales (30D)", value: "\u20B928,75,000", change: "+8.2% from yesterday", change_type: "positive" as const, icon: TrendingUp },
  { title: "Orders Today", value: "186", change: "+18 from yesterday", change_type: "positive" as const, icon: ShoppingCart },
  { title: "Units Today", value: "342", change: "+24 from yesterday", change_type: "positive" as const, icon: Package },
  { title: "Return Rate", value: "3.8%", change: "+1.0% from yesterday", change_type: "negative" as const, icon: RotateCcw },
  { title: "Stockout Risks", value: "5", change: "Critical from yesterday", change_type: "negative" as const, icon: AlertTriangle },
];

// Generate 30 days of fake line data
const LINE_DATA = Array.from({ length: 30 }, (_, i) => ({
  date: `Feb ${i + 1}`,
  sales: Math.floor(60000 + Math.random() * 60000),
}));

const PIE_DATA = [
  { name: "Amazon.in", value: 43.5, color: "#F97316" },
  { name: "Flipkart", value: 31, color: "#3B82F6" },
  { name: "Shopify", value: 21.7, color: "#22C55E" },
  { name: "Facebook", value: 3.8, color: "#8B5CF6" },
];

const ALERTS = [
  { type: "critical", icon: AlertCircle, message: "Low Stock Alert", detail: "SWD-CHAI-250 will stockout in 8 days" },
];

export function DashboardPage() {
  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-2xl font-bold">Command Center</h2>
        <p className="text-muted-foreground">Real-time overview of your multi-marketplace business</p>
      </div>

      {/* KPI Cards */}
      <div className="grid grid-cols-2 gap-4 md:grid-cols-3 lg:grid-cols-6">
        {KPI_DATA.map((kpi) => (
          <KPICard key={kpi.title} {...kpi} />
        ))}
      </div>

      {/* Charts */}
      <div className="grid gap-6 lg:grid-cols-3">
        {/* Line chart */}
        <Card className="p-6 lg:col-span-2">
          <h3 className="mb-4 font-semibold">Net Sales Trend (Last 30 Days)</h3>
          <ResponsiveContainer width="100%" height={250}>
            <LineChart data={LINE_DATA}>
              <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
              <XAxis dataKey="date" tick={{ fontSize: 11 }} interval={4} />
              <YAxis
                tick={{ fontSize: 11 }}
                tickFormatter={(v) => `\u20B9${(v / 1000).toFixed(0)}k`}
              />
              <Tooltip
                formatter={(value) =>
                  [`\u20B9${Number(value).toLocaleString("en-IN")}`, "Net Sales"]
                }
              />
              <Line
                type="monotone"
                dataKey="sales"
                stroke="#F97316"
                strokeWidth={2}
                dot={false}
              />
            </LineChart>
          </ResponsiveContainer>
        </Card>

        {/* Donut chart */}
        <Card className="p-6">
          <h3 className="mb-4 font-semibold">Sales by Marketplace</h3>
          <ResponsiveContainer width="100%" height={250}>
            <PieChart>
              <Pie
                data={PIE_DATA}
                cx="50%"
                cy="50%"
                innerRadius={50}
                outerRadius={80}
                paddingAngle={2}
                dataKey="value"
              >
                {PIE_DATA.map((entry) => (
                  <Cell key={entry.name} fill={entry.color} />
                ))}
              </Pie>
              <Legend
                formatter={(value: string, entry: any) => (
                  <span className="text-xs">
                    {value} {entry.payload.value}%
                  </span>
                )}
              />
            </PieChart>
          </ResponsiveContainer>
        </Card>
      </div>

      {/* Alerts */}
      <Card className="p-6">
        <div className="mb-4 flex items-center justify-between">
          <h3 className="font-semibold">Alerts & Recommendations</h3>
          <Badge variant="destructive">{ALERTS.length} Critical</Badge>
        </div>
        <div className="space-y-3">
          {ALERTS.map((alert, i) => (
            <div key={i} className="flex items-center gap-3 rounded-lg border p-3">
              <alert.icon className="h-5 w-5 text-red-500" />
              <div>
                <div className="text-sm font-medium">{alert.message}</div>
                <div className="text-xs text-muted-foreground">{alert.detail}</div>
              </div>
            </div>
          ))}
        </div>
      </Card>
    </div>
  );
}
