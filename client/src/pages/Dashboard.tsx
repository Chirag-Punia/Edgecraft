import { useState, useEffect, useMemo, useCallback, useRef } from "react";
import api from "@/lib/api";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { KPICard } from "@/components/dashboard/KPICard";
import { SectionHeader } from "@/components/dashboard/SectionHeader";
import { InfoTip } from "@/components/dashboard/InfoTip";
import {
  IndianRupee,
  ShoppingCart,
  Receipt,
  XCircle,
  Trophy,
  AlertTriangle,
  AlertCircle,
  Database,
  Loader2,
  CheckCircle2,
  PackageX,
  Trash2,
  MapPin,
  TrendingDown,
  MessageSquareWarning,
  ChevronRight,
} from "lucide-react";
import {
  LineChart,
  Line,
  BarChart,
  Bar,
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

// ── Types ──────────────────────────────────────────────

interface SalesTrendPoint { day: string; gmv: number; order_count: number }
interface OrderStatusItem { status: string; count: number }
interface TopProduct { asin: string; title: string; revenue: number; units_sold: number }
interface InventoryHealth {
  summary: { total_skus: number; low_stock: number; healthy: number; overstocked: number };
  flagged_items: { seller_sku: string; asin: string | null; product_name: string | null; fulfillable: number; inbound: number; total: number }[];
}
interface PricingOverview {
  total_products: number; winning_count: number; win_rate: number;
  losing_items: { asin: string; product_name: string | null; your_price: number; buybox_price: number; gap: number }[];
}
interface ActionItem { severity: string; category: string; title: string; detail: string }
interface DemandForecastItem { asin: string; product_name: string; predicted_units: number; velocity_7d: number; days_of_stock: number | null; stockout_risk: boolean }
interface SentimentOverview { avg_sentiment: number | null; total_reviews: number; data: SentimentItem[] }
interface SentimentItem { asin: string; product_name: string; avg_sentiment: number; positive: number; negative: number; neutral: number; top_complaints: string[] }
interface CitySalesItem { city: string; state: string | null; revenue: number; order_count: number }
interface KPI { title: string; value: string; change: string; change_type: "positive" | "negative" | "neutral" }

// ── Constants ──────────────────────────────────────────

const KPI_ICONS = [IndianRupee, ShoppingCart, Receipt, XCircle, Trophy, AlertTriangle];
const KPI_INFO = [
  "Total order revenue in the selected period, compared to the same-length prior period.",
  "Number of orders placed in the selected period vs the prior period.",
  "Average order value = total revenue / total orders in the selected period.",
  "Percentage of orders cancelled or returned out of all orders in the period.",
  "% of your products winning the Buy Box based on latest pricing snapshot data.",
  "Products predicted to run out of stock within 7 days based on demand forecast velocity.",
];
const PERIOD_OPTIONS = [
  { value: 7, label: "7 Days" },
  { value: 30, label: "30 Days" },
  { value: 90, label: "90 Days" },
];
const STATUS_COLORS: Record<string, string> = {
  Pending: "#F59E0B", Shipped: "#3B82F6", Delivered: "#22C55E", Cancelled: "#EF4444", Unshipped: "#8B5CF6",
};
const SEVERITY_STYLES: Record<string, { icon: string; border: string; bg: string }> = {
  critical: { icon: "text-red-500", border: "border-red-200", bg: "bg-red-50" },
  warning: { icon: "text-amber-500", border: "border-amber-200", bg: "bg-amber-50" },
  info: { icon: "text-blue-500", border: "border-blue-200", bg: "bg-blue-50" },
};

function fmtINR(n: number) {
  return "₹" + n.toLocaleString("en-IN", { maximumFractionDigits: 0 });
}

// ── Component ──────────────────────────────────────────

export function DashboardPage() {
  const [days, setDays] = useState(30);
  const [seeding, setSeeding] = useState(false);
  const [unseeding, setUnseeding] = useState(false);
  const [seedResult, setSeedResult] = useState<{ message: string; isError: boolean } | null>(null);
  const [isSeeded, setIsSeeded] = useState(false);
  const [loading, setLoading] = useState(true);

  // Data state
  const [kpis, setKpis] = useState<KPI[]>([]);
  const [salesTrend, setSalesTrend] = useState<SalesTrendPoint[]>([]);
  const [orderStatus, setOrderStatus] = useState<OrderStatusItem[]>([]);
  const [topProducts, setTopProducts] = useState<TopProduct[]>([]);
  const [inventory, setInventory] = useState<InventoryHealth | null>(null);
  const [pricing, setPricing] = useState<PricingOverview | null>(null);
  const [actionItems, setActionItems] = useState<ActionItem[]>([]);
  const [forecast, setForecast] = useState<DemandForecastItem[]>([]);
  const [sentiment, setSentiment] = useState<SentimentOverview | null>(null);
  const [citySales, setCitySales] = useState<CitySalesItem[]>([]);

  // Snapshot-based endpoints (don't depend on time period)
  const fetchSnapshot = useCallback(() => {
    Promise.allSettled([
      api.get("/dashboard/inventory-health"),
      api.get("/dashboard/pricing-overview"),
      api.get("/dashboard/action-items"),
      api.get("/dashboard/demand-forecast"),
      api.get("/dashboard/sentiment-overview"),
    ]).then(([ihR, poR, aiR, dfR, soR]) => {
      if (ihR.status === "fulfilled") setInventory(ihR.value.data);
      if (poR.status === "fulfilled") setPricing(poR.value.data);
      if (aiR.status === "fulfilled") setActionItems(aiR.value.data.items);
      if (dfR.status === "fulfilled") setForecast(dfR.value.data.data);
      if (soR.status === "fulfilled") setSentiment(soR.value.data);
    });
  }, []);

  // Time-period endpoints
  const fetchTimeSeries = useCallback((period: number) => {
    const q = `?days=${period}`;
    return Promise.allSettled([
      api.get(`/dashboard/kpis${q}`),
      api.get(`/dashboard/sales-trend${q}`),
      api.get(`/dashboard/order-status${q}`),
      api.get(`/dashboard/top-products${q}`),
      api.get(`/dashboard/city-sales${q}`),
    ]).then(([kR, stR, osR, tpR, csR]) => {
      if (kR.status === "fulfilled") setKpis(kR.value.data.kpis);
      if (stR.status === "fulfilled") setSalesTrend(stR.value.data.data);
      if (osR.status === "fulfilled") setOrderStatus(osR.value.data.data);
      if (tpR.status === "fulfilled") setTopProducts(tpR.value.data.data);
      if (csR.status === "fulfilled") setCitySales(csR.value.data.data);
    });
  }, []);

  const [autoSeeding, setAutoSeeding] = useState(false);
  const seedPollRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const abortRef = useRef<AbortController | null>(null);

  // Fetch dashboard data with retry for eventual consistency
  const fetchAllData = useCallback(async (period: number, retryOnEmpty = true) => {
    await Promise.all([fetchTimeSeries(period), fetchSnapshot()]);
    // If KPIs came back empty and this is the first attempt, retry after a delay
    // (DynamoDB GSI eventual consistency may cause briefly empty results)
    if (retryOnEmpty) {
      // We need to check the state after the fetch; use a short timeout to re-fetch
      await new Promise((resolve) => setTimeout(resolve, 2000));
      await Promise.all([fetchTimeSeries(period), fetchSnapshot()]);
    }
  }, [fetchTimeSeries, fetchSnapshot]);

  // Poll demo-status until seeded, then fetch data
  const startSeedPolling = useCallback((period: number) => {
    // Clear any existing poll
    if (seedPollRef.current) {
      clearInterval(seedPollRef.current);
      seedPollRef.current = null;
    }
    setAutoSeeding(true);
    let attempt = 0;
    const maxAttempts = 20;
    seedPollRef.current = setInterval(() => {
      // Check if the component has unmounted (abort signal fired)
      if (abortRef.current?.signal.aborted) {
        clearInterval(seedPollRef.current!);
        seedPollRef.current = null;
        return;
      }
      attempt++;
      api.get("/sync/demo-status").then(({ data: d }) => {
        // Guard against updates after unmount
        if (abortRef.current?.signal.aborted) return;
        if (d.is_seeded) {
          clearInterval(seedPollRef.current!);
          seedPollRef.current = null;
          setIsSeeded(true);
          setAutoSeeding(false);
          // Delay slightly for DynamoDB GSI eventual consistency, then fetch
          setTimeout(() => {
            if (abortRef.current?.signal.aborted) return;
            fetchAllData(period, true).then(() => {
              if (!abortRef.current?.signal.aborted) setLoading(false);
            });
          }, 1000);
        } else if (!d.is_seeding && attempt >= 3) {
          // Not seeding and not seeded — no background job running
          clearInterval(seedPollRef.current!);
          seedPollRef.current = null;
          setAutoSeeding(false);
          setLoading(false);
        } else if (attempt >= maxAttempts) {
          clearInterval(seedPollRef.current!);
          seedPollRef.current = null;
          setAutoSeeding(false);
          setLoading(false);
        }
      }).catch(() => {
        if (attempt >= maxAttempts) {
          clearInterval(seedPollRef.current!);
          seedPollRef.current = null;
          setAutoSeeding(false);
          setLoading(false);
        }
      });
    }, 3000);
  }, [fetchAllData]);

  useEffect(() => {
    const controller = new AbortController();
    abortRef.current = controller;
    setLoading(true);

    api.get("/sync/demo-status", { signal: controller.signal }).then(({ data }) => {
      if (controller.signal.aborted) return;
      if (data.is_seeded) {
        setIsSeeded(true);
        fetchAllData(days, false).then(() => {
          if (!controller.signal.aborted) setLoading(false);
        });
      } else if (data.is_seeding) {
        // Background auto-seed is running; poll for completion
        if (!controller.signal.aborted) startSeedPolling(days);
      } else {
        // Not seeded and not seeding
        setLoading(false);
      }
    }).catch(() => {
      // Ignore errors if aborted (expected on StrictMode unmount)
      if (!controller.signal.aborted) setLoading(false);
    });

    return () => {
      controller.abort();
      if (seedPollRef.current) {
        clearInterval(seedPollRef.current);
        seedPollRef.current = null;
      }
    };
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  const handlePeriodChange = (newDays: number) => {
    setDays(newDays);
    fetchTimeSeries(newDays);
  };

  const handleSeedDemo = async () => {
    setSeeding(true);
    setSeedResult(null);
    try {
      const { data } = await api.post("/sync/seed-demo");
      setSeedResult({ message: data.message, isError: false });
      // Don't fetch data immediately — seed runs in background
      // Start polling for completion
      setSeeding(false);
      setLoading(true);
      startSeedPolling(days);
    } catch (err: any) {
      setSeedResult({ message: err.response?.data?.detail || "Failed to seed demo data", isError: true });
      setSeeding(false);
    }
  };

  const clearDashboardData = useCallback(() => {
    setKpis([]);
    setSalesTrend([]);
    setOrderStatus([]);
    setTopProducts([]);
    setInventory(null);
    setPricing(null);
    setActionItems([]);
    setForecast([]);
    setSentiment(null);
    setCitySales([]);
  }, []);

  const handleUnseedDemo = async () => {
    setUnseeding(true);
    setSeedResult(null);
    try {
      const { data } = await api.post("/sync/unseed");
      setSeedResult({ message: data.message, isError: false });
      setIsSeeded(false);
      clearDashboardData();
    } catch (err: any) {
      setSeedResult({ message: err.response?.data?.detail || "Failed to remove demo data", isError: true });
    } finally {
      setUnseeding(false);
    }
  };

  // Top products as bar chart data (truncate labels)
  const productChartData = useMemo(
    () => topProducts.slice(0, 7).map((p) => ({
      name: p.title.length > 18 ? p.title.slice(0, 16) + "…" : p.title,
      revenue: Math.round(p.revenue),
      units: p.units_sold,
    })),
    [topProducts],
  );

  return (
    <div className="space-y-8">
      {/* ── Header ── */}
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 className="text-2xl font-bold tracking-tight">Dashboard</h2>
          <p className="text-sm text-muted-foreground">Your business at a glance</p>
        </div>
        <div className="flex items-center gap-3">
          {/* Period Selector - pill-shaped segments */}
          <div className="flex rounded-full border bg-muted p-0.5">
            {PERIOD_OPTIONS.map((opt) => (
              <button
                key={opt.value}
                onClick={() => handlePeriodChange(opt.value)}
                className={`rounded-full px-4 py-1.5 text-xs font-medium transition-all ${
                  days === opt.value
                    ? "bg-primary text-primary-foreground shadow-sm"
                    : "text-muted-foreground hover:text-foreground"
                }`}
              >
                {opt.label}
              </button>
            ))}
          </div>

          {seedResult && (
            <span className={`flex items-center gap-1 text-xs ${seedResult.isError ? "text-red-600" : "text-green-600"}`}>
              {seedResult.isError ? <XCircle className="h-3.5 w-3.5" /> : <CheckCircle2 className="h-3.5 w-3.5" />}
              {seedResult.message}
            </span>
          )}
          {isSeeded ? (
            <Button variant="destructive" size="sm" className="h-7 text-xs" onClick={handleUnseedDemo} disabled={unseeding}>
              {unseeding ? <><Loader2 className="mr-2 h-3.5 w-3.5 animate-spin" />Removing...</> : <><Trash2 className="mr-2 h-3.5 w-3.5" />Unseed</>}
            </Button>
          ) : (
            <Button variant="outline" size="sm" className="h-7 text-xs" onClick={handleSeedDemo} disabled={seeding}>
              {seeding ? <><Loader2 className="mr-2 h-3.5 w-3.5 animate-spin" />Seeding...</> : <><Database className="mr-2 h-3.5 w-3.5" />Seed Demo</>}
            </Button>
          )}
        </div>
      </div>

      {loading ? (
        <div className="flex flex-col items-center justify-center py-20 gap-3">
          <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
          {autoSeeding && (
            <p className="text-sm text-muted-foreground">Setting up your dashboard with demo data...</p>
          )}
        </div>
      ) : (
        <>
          {/* ── KPI Cards ── */}
          <div className="grid grid-cols-2 gap-4 md:grid-cols-3 lg:grid-cols-3">
            {kpis.map((kpi, i) => {
              const delays = ["", "delay-75", "delay-150", "delay-225", "delay-300", "delay-375"];
              return (
                <div key={kpi.title} className={`animate-slide-up ${delays[i] || ""}`}>
                  <KPICard {...kpi} icon={KPI_ICONS[i] || AlertTriangle} info={KPI_INFO[i]} />
                </div>
              );
            })}
          </div>

          {/* ── Action Items (if any) ── */}
          {actionItems.length > 0 && (
            <Card className="p-5">
              <div className="mb-3 flex items-center justify-between">
                <h3 className="font-semibold flex items-center gap-2">
                  <AlertCircle className="h-4 w-4 text-red-500" />
                  Action Items
                  <InfoTip text="Auto-generated from stockout forecasts, pricing gaps, negative reviews, and pending shipments. Critical = needs immediate action." />
                </h3>
                <Badge variant={actionItems.some((a) => a.severity === "critical") ? "destructive" : "secondary"}>
                  {actionItems.length}
                </Badge>
              </div>
              <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
                {actionItems.slice(0, 6).map((item, i) => {
                  const style = SEVERITY_STYLES[item.severity] || SEVERITY_STYLES.info;
                  return (
                    <div key={i} className={`flex items-start gap-3 rounded-lg border ${style.border} ${style.bg} p-3`}>
                      <ChevronRight className={`mt-0.5 h-4 w-4 shrink-0 ${style.icon}`} />
                      <div className="min-w-0">
                        <div className="text-sm font-medium truncate">{item.title}</div>
                        <div className="text-xs text-muted-foreground line-clamp-2">{item.detail}</div>
                      </div>
                    </div>
                  );
                })}
              </div>
            </Card>
          )}

          {/* ── Sales Overview ── */}
          <SectionHeader title="Sales Overview" subtitle="Revenue trends and order distribution" />
          <div className="grid gap-6 lg:grid-cols-3 animate-slide-up delay-150">
            <Card className="p-6 lg:col-span-2">
              <h3 className="mb-4 font-semibold flex items-center gap-1.5">Sales Trend (Last {days} Days) <InfoTip text="Daily revenue (purple, left axis) and order count (blue, right axis) over the selected time period." /></h3>
              {salesTrend.length > 0 ? (
                <ResponsiveContainer width="100%" height={260}>
                  <LineChart data={salesTrend}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
                    <XAxis
                      dataKey="day"
                      tick={{ fontSize: 11 }}
                      interval={Math.max(0, Math.floor(salesTrend.length / 7) - 1)}
                      tickFormatter={(v) => {
                        const d = new Date(v);
                        return `${d.getDate()}/${d.getMonth() + 1}`;
                      }}
                    />
                    <YAxis yAxisId="left" tick={{ fontSize: 11 }} tickFormatter={(v) => `₹${(v / 1000).toFixed(0)}k`} />
                    <YAxis yAxisId="right" orientation="right" tick={{ fontSize: 11 }} />
                    <Tooltip
                      formatter={(value: number | string | undefined, name?: string) => {
                        const isRevenue = name === "gmv";
                        const formatted =
                          typeof value === "number" ? (isRevenue ? fmtINR(value) : value) : value;
                        if (name == null) return formatted;
                        return [formatted, isRevenue ? "Revenue" : "Orders"];
                      }}
                      labelFormatter={(v) => new Date(v).toLocaleDateString("en-IN")}
                    />
                    <Line type="monotone" dataKey="gmv" stroke="#7C3AED" strokeWidth={2} dot={false} name="gmv" yAxisId="left" />
                    <Line type="monotone" dataKey="order_count" stroke="#3B82F6" strokeWidth={1.5} dot={false} name="orders" yAxisId="right" />
                  </LineChart>
                </ResponsiveContainer>
              ) : (
                <p className="py-10 text-center text-muted-foreground text-sm">No sales data. Seed demo data to get started.</p>
              )}
            </Card>

            <Card className="p-6">
              <h3 className="mb-4 font-semibold flex items-center gap-1.5">Order Status <InfoTip text="Distribution of orders by status (Pending, Shipped, Delivered, Cancelled) in the selected period." /></h3>
              {orderStatus.length > 0 ? (
                <ResponsiveContainer width="100%" height={260}>
                  <PieChart>
                    <Pie
                      data={orderStatus}
                      cx="50%"
                      cy="50%"
                      innerRadius={50}
                      outerRadius={80}
                      paddingAngle={2}
                      dataKey="count"
                      nameKey="status"
                    >
                      {orderStatus.map((entry) => (
                        <Cell key={entry.status} fill={STATUS_COLORS[entry.status] || "#94A3B8"} />
                      ))}
                    </Pie>
                    <Legend formatter={(value: string, entry: any) => <span className="text-xs">{value} ({entry.payload.count})</span>} />
                  </PieChart>
                </ResponsiveContainer>
              ) : (
                <p className="py-10 text-center text-muted-foreground text-sm">No order data yet.</p>
              )}
            </Card>
          </div>

          {/* ── Product Intelligence ── */}
          <SectionHeader title="Product Intelligence" subtitle="Top performers and geographic distribution" />
          <div className="grid gap-6 lg:grid-cols-2 animate-slide-up delay-225">
            <Card className="p-6">
              <h3 className="mb-4 font-semibold flex items-center gap-1.5">Top Products by Revenue <InfoTip text="Top 7 products ranked by total revenue (unit price × quantity) from orders in the selected period." /></h3>
              {productChartData.length > 0 ? (
                <ResponsiveContainer width="100%" height={280}>
                  <BarChart data={productChartData} layout="vertical" margin={{ left: 10, right: 20 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
                    <XAxis type="number" tick={{ fontSize: 11 }} tickFormatter={(v) => `₹${(v / 1000).toFixed(0)}k`} />
                    <YAxis type="category" dataKey="name" tick={{ fontSize: 10 }} width={120} />
                    <Tooltip
                      formatter={(v: number | string | undefined) => {
                        const formatted = typeof v === "number" ? fmtINR(v) : v;
                        return [formatted, "Revenue"];
                      }}
                    />
                    <Bar dataKey="revenue" fill="#7C3AED" radius={[0, 4, 4, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              ) : (
                <p className="py-10 text-center text-muted-foreground text-sm">No product data yet.</p>
              )}
            </Card>

            <Card className="p-6">
              <h3 className="mb-4 font-semibold flex items-center gap-2">
                <MapPin className="h-4 w-4 text-muted-foreground" />
                Top Cities by Revenue
                <InfoTip text="Revenue aggregated by shipping city from orders in the selected period. Top 8 cities shown." />
              </h3>
              {citySales.length > 0 ? (
                <ResponsiveContainer width="100%" height={280}>
                  <BarChart data={citySales.slice(0, 8)} layout="vertical" margin={{ left: 10, right: 20 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
                    <XAxis type="number" tick={{ fontSize: 11 }} tickFormatter={(v) => `₹${(v / 1000).toFixed(0)}k`} />
                    <YAxis type="category" dataKey="city" tick={{ fontSize: 11 }} width={90} />
                    <Tooltip
                      formatter={(v: number | string | undefined, name?: string) => {
                        const isRevenue = name === "revenue";
                        const formatted =
                          typeof v === "number"
                            ? isRevenue
                              ? fmtINR(v)
                              : `${v} orders`
                            : v;
                        if (name == null) return formatted;
                        return [formatted, isRevenue ? "Revenue" : "Orders"];
                      }}
                    />
                    <Bar dataKey="revenue" fill="#3B82F6" radius={[0, 4, 4, 0]} name="revenue" />
                  </BarChart>
                </ResponsiveContainer>
              ) : (
                <p className="py-10 text-center text-muted-foreground text-sm">No city-level data yet.</p>
              )}
            </Card>
          </div>

          {/* ── Operations ── */}
          <SectionHeader title="Operations" subtitle="Demand forecasting and inventory management" />
          <div className="grid gap-6 lg:grid-cols-2 animate-slide-up delay-300">
            {/* Demand Forecast */}
            <Card className="p-6">
              <h3 className="mb-4 font-semibold flex items-center gap-2">
                <TrendingDown className="h-4 w-4 text-muted-foreground" />
                Demand Forecast (7-day)
                <InfoTip text="Predicted unit sales for the next 7 days using recent velocity. 'Days Left' = current stock / daily velocity. AT RISK = likely to stock out within 7 days." />
              </h3>
              {forecast.length > 0 ? (
                <div className="overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="border-b text-left text-muted-foreground">
                        <th className="pb-2 pr-3">Product</th>
                        <th className="pb-2 pr-3 text-right">Predicted</th>
                        <th className="pb-2 pr-3 text-right">Velocity/d</th>
                        <th className="pb-2 pr-3 text-right">Days Left</th>
                        <th className="pb-2 text-center">Risk</th>
                      </tr>
                    </thead>
                    <tbody>
                      {forecast.slice(0, 8).map((f) => (
                        <tr key={f.asin} className="border-b last:border-0">
                          <td className="py-2 pr-3">
                            <div className="font-medium truncate max-w-[180px]">{f.product_name}</div>
                          </td>
                          <td className="py-2 pr-3 text-right">{f.predicted_units}</td>
                          <td className="py-2 pr-3 text-right">{f.velocity_7d.toFixed(1)}</td>
                          <td className="py-2 pr-3 text-right">{f.days_of_stock ?? "—"}</td>
                          <td className="py-2 text-center">
                            {f.stockout_risk ? (
                              <Badge variant="destructive" className="text-[10px]">AT RISK</Badge>
                            ) : (
                              <Badge variant="secondary" className="text-[10px]">OK</Badge>
                            )}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              ) : (
                <p className="py-10 text-center text-muted-foreground text-sm">No forecast data. Run demand forecasting first.</p>
              )}
            </Card>

            {/* Inventory Health */}
            <Card className="p-6">
              <h3 className="mb-4 font-semibold flex items-center gap-1.5">Inventory Health <InfoTip text="Latest inventory snapshot. Low stock = ≤10 fulfillable units. Overstock = ≥150 units. Flagged items shown below the summary." /></h3>
              {inventory && inventory.summary.total_skus > 0 ? (
                <>
                  <div className="mb-4 grid grid-cols-4 gap-3">
                    <div className="rounded-lg bg-muted p-3 text-center">
                      <div className="text-lg font-bold">{inventory.summary.total_skus}</div>
                      <div className="text-xs text-muted-foreground">Total SKUs</div>
                    </div>
                    <div className="rounded-lg bg-red-50 p-3 text-center">
                      <div className="text-lg font-bold text-red-600">{inventory.summary.low_stock}</div>
                      <div className="text-xs text-muted-foreground">Low Stock</div>
                    </div>
                    <div className="rounded-lg bg-green-50 p-3 text-center">
                      <div className="text-lg font-bold text-green-600">{inventory.summary.healthy}</div>
                      <div className="text-xs text-muted-foreground">Healthy</div>
                    </div>
                    <div className="rounded-lg bg-amber-50 p-3 text-center">
                      <div className="text-lg font-bold text-amber-600">{inventory.summary.overstocked}</div>
                      <div className="text-xs text-muted-foreground">Overstock</div>
                    </div>
                  </div>
                  {inventory.flagged_items.length > 0 && (
                    <>
                      <h4 className="mb-2 text-sm font-medium text-red-600 flex items-center gap-1">
                        <PackageX className="h-4 w-4" /> Low Stock Items
                      </h4>
                      <div className="space-y-1">
                        {inventory.flagged_items.slice(0, 5).map((item) => (
                          <div key={item.seller_sku} className="flex items-center justify-between rounded border px-3 py-2 text-sm">
                            <span className="truncate max-w-[200px]">{item.product_name || item.seller_sku}</span>
                            <Badge variant={item.fulfillable <= 3 ? "destructive" : "secondary"}>
                              {item.fulfillable} units
                            </Badge>
                          </div>
                        ))}
                      </div>
                    </>
                  )}
                </>
              ) : (
                <p className="py-10 text-center text-muted-foreground text-sm">No inventory data yet.</p>
              )}
            </Card>
          </div>

          {/* ── Market Position ── */}
          <SectionHeader title="Market Position" subtitle="Pricing competitiveness and customer feedback" />
          <div className="grid gap-6 lg:grid-cols-2 animate-slide-up delay-375">
            {/* Pricing / Buy Box */}
            <Card className="p-6">
              <h3 className="mb-4 font-semibold flex items-center gap-1.5">Buy Box Performance <InfoTip text="Win rate = % of your products currently winning the Amazon Buy Box. Products losing the Buy Box are listed with the price gap to match." /></h3>
              {pricing && pricing.total_products > 0 ? (
                <>
                  <div className="mb-4 flex items-center gap-6">
                    <div className="flex items-center gap-2">
                      <Trophy className="h-5 w-5 text-amber-500" />
                      <div>
                        <div className="text-2xl font-bold">{pricing.win_rate}%</div>
                        <div className="text-xs text-muted-foreground">Win Rate</div>
                      </div>
                    </div>
                    <div className="text-sm text-muted-foreground">
                      {pricing.winning_count} of {pricing.total_products} products winning
                    </div>
                  </div>
                  {pricing.losing_items.length > 0 && (
                    <>
                      <h4 className="mb-2 text-sm font-medium text-red-600 flex items-center gap-1">
                        Not Winning Buy Box
                      </h4>
                      <div className="overflow-x-auto">
                        <table className="w-full text-sm">
                          <thead>
                            <tr className="border-b text-left text-muted-foreground">
                              <th className="pb-2 pr-4">Product</th>
                              <th className="pb-2 pr-4 text-right">Your Price</th>
                              <th className="pb-2 pr-4 text-right">Buy Box</th>
                              <th className="pb-2 text-right">Gap</th>
                            </tr>
                          </thead>
                          <tbody>
                            {pricing.losing_items.slice(0, 5).map((item) => (
                              <tr key={item.asin} className="border-b last:border-0">
                                <td className="py-2 pr-4 truncate max-w-[180px]">{item.product_name || item.asin}</td>
                                <td className="py-2 pr-4 text-right">{fmtINR(item.your_price)}</td>
                                <td className="py-2 pr-4 text-right">{fmtINR(item.buybox_price)}</td>
                                <td className="py-2 text-right text-red-600">+₹{item.gap.toFixed(0)}</td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                    </>
                  )}
                </>
              ) : (
                <p className="py-10 text-center text-muted-foreground text-sm">No pricing data yet.</p>
              )}
            </Card>

            {/* Sentiment Overview */}
            <Card className="p-6">
              <h3 className="mb-4 font-semibold flex items-center gap-2">
                <MessageSquareWarning className="h-4 w-4 text-muted-foreground" />
                Customer Sentiment
                <InfoTip text="Sentiment score (-1 to +1) computed from customer reviews. Green = positive, red = negative. Top complaints extracted per product." />
              </h3>
              {sentiment && sentiment.data.length > 0 ? (
                <>
                  <div className="mb-4 flex items-center gap-6">
                    <div>
                      <div className="text-2xl font-bold">
                        {sentiment.avg_sentiment !== null ? (sentiment.avg_sentiment > 0 ? "+" : "") + sentiment.avg_sentiment.toFixed(2) : "--"}
                      </div>
                      <div className="text-xs text-muted-foreground">Avg Sentiment (-1 to +1)</div>
                    </div>
                    <div className="text-sm text-muted-foreground">{sentiment.total_reviews} total reviews</div>
                  </div>
                  <div className="space-y-2">
                    {sentiment.data.slice(0, 5).map((item) => {
                      const total = item.positive + item.negative + item.neutral || 1;
                      const posWidth = Math.round((item.positive / total) * 100);
                      const negWidth = Math.round((item.negative / total) * 100);
                      return (
                        <div key={item.asin}>
                          <div className="flex items-center justify-between text-sm mb-1">
                            <span className="truncate max-w-[200px] font-medium">{item.product_name}</span>
                            <span className={`text-xs ${item.avg_sentiment >= 0 ? "text-green-600" : "text-red-600"}`}>
                              {item.avg_sentiment >= 0 ? "+" : ""}{item.avg_sentiment.toFixed(2)}
                            </span>
                          </div>
                          <div className="flex h-2 w-full rounded-full overflow-hidden bg-gray-100">
                            <div className="bg-green-500" style={{ width: `${posWidth}%` }} />
                            <div className="bg-gray-300" style={{ width: `${100 - posWidth - negWidth}%` }} />
                            <div className="bg-red-500" style={{ width: `${negWidth}%` }} />
                          </div>
                          {item.top_complaints.length > 0 && (
                            <div className="text-[10px] text-muted-foreground mt-0.5">
                              Issues: {item.top_complaints.join(", ")}
                            </div>
                          )}
                        </div>
                      );
                    })}
                  </div>
                </>
              ) : (
                <p className="py-10 text-center text-muted-foreground text-sm">No review data yet.</p>
              )}
            </Card>
          </div>
        </>
      )}
    </div>
  );
}
