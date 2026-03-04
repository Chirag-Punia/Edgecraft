import { useState, useEffect, useMemo } from "react";
import api from "@/lib/api";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { KPICard } from "@/components/dashboard/KPICard";
import {
  IndianRupee,
  TrendingUp,
  ShoppingCart,
  Package,
  RotateCcw,
  AlertTriangle,
  AlertCircle,
  Database,
  Loader2,
  CheckCircle2,
  Trophy,
  PackageX,
  ArrowDown,
  Trash2,
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

const KPI_ICONS = [IndianRupee, TrendingUp, ShoppingCart, Package, RotateCcw, AlertTriangle];
const STATUS_COLORS: Record<string, string> = {
  Pending: "#F59E0B",
  Shipped: "#3B82F6",
  Delivered: "#22C55E",
  Cancelled: "#EF4444",
};

interface SalesTrendPoint { day: string; gmv: number }
interface OrderStatusItem { status: string; count: number }
interface TopProduct { asin: string; title: string; revenue: number; units_sold: number }
interface InventoryHealth {
  summary: { total_skus: number; low_stock: number; healthy: number; overstocked: number };
  flagged_items: { seller_sku: string; asin: string | null; fulfillable: number; inbound: number; total: number }[];
}
interface PricingOverview {
  total_products: number; winning_count: number; win_rate: number;
  losing_items: { asin: string; your_price: number; buybox_price: number; gap: number }[];
}
interface KPI { title: string; value: string; change: string; change_type: "positive" | "negative" | "neutral" }

function fmtINR(n: number) {
  return "₹" + n.toLocaleString("en-IN", { maximumFractionDigits: 0 });
}

export function DashboardPage() {
  const [seeding, setSeeding] = useState(false);
  const [unseeding, setUnseeding] = useState(false);
  const [seedResult, setSeedResult] = useState<string | null>(null);
  const [isSeeded, setIsSeeded] = useState(false);
  const [loading, setLoading] = useState(true);

  const [kpis, setKpis] = useState<KPI[]>([]);
  const [salesTrend, setSalesTrend] = useState<SalesTrendPoint[]>([]);
  const [orderStatus, setOrderStatus] = useState<OrderStatusItem[]>([]);
  const [topProducts, setTopProducts] = useState<TopProduct[]>([]);
  const [inventory, setInventory] = useState<InventoryHealth | null>(null);
  const [pricing, setPricing] = useState<PricingOverview | null>(null);

  const fetchAll = () => {
    setLoading(true);
    Promise.allSettled([
      api.get("/dashboard/kpis"),
      api.get("/dashboard/sales-trend"),
      api.get("/dashboard/order-status"),
      api.get("/dashboard/top-products"),
      api.get("/dashboard/inventory-health"),
      api.get("/dashboard/pricing-overview"),
    ]).then(([kR, stR, osR, tpR, ihR, poR]) => {
      if (kR.status === "fulfilled") setKpis(kR.value.data.kpis);
      if (stR.status === "fulfilled") setSalesTrend(stR.value.data.data);
      if (osR.status === "fulfilled") setOrderStatus(osR.value.data.data);
      if (tpR.status === "fulfilled") setTopProducts(tpR.value.data.data);
      if (ihR.status === "fulfilled") setInventory(ihR.value.data);
      if (poR.status === "fulfilled") setPricing(poR.value.data);
      setLoading(false);
    });
  };

  const fetchDemoStatus = () => {
    api.get("/sync/demo-status").then(({ data }) => {
      setIsSeeded(data.is_seeded);
    }).catch(() => {});
  };

  useEffect(() => {
    fetchDemoStatus();
    fetchAll();
  }, []);

  const handleSeedDemo = async () => {
    setSeeding(true);
    setSeedResult(null);
    try {
      const { data } = await api.post("/sync/seed-demo");
      setSeedResult(data.message);
      setIsSeeded(true);
      fetchAll();
    } catch (err: any) {
      setSeedResult(err.response?.data?.detail || "Failed to seed demo data");
    } finally {
      setSeeding(false);
    }
  };

  const handleUnseedDemo = async () => {
    setUnseeding(true);
    setSeedResult(null);
    try {
      const { data } = await api.post("/sync/unseed");
      setSeedResult(data.message);
      setIsSeeded(false);
      fetchAll();
    } catch (err: any) {
      setSeedResult(err.response?.data?.detail || "Failed to remove demo data");
    } finally {
      setUnseeding(false);
    }
  };

  // Auto-generated alerts from inventory + pricing
  const alerts = useMemo(() => {
    const list: { type: "critical" | "warning"; message: string; detail: string }[] = [];
    if (inventory && inventory.summary.low_stock > 0) {
      list.push({
        type: "critical",
        message: `Low Stock Alert`,
        detail: `${inventory.summary.low_stock} SKU(s) with stock ≤ 10 units`,
      });
    }
    if (inventory && inventory.summary.overstocked > 0) {
      list.push({
        type: "warning",
        message: "Overstock Warning",
        detail: `${inventory.summary.overstocked} SKU(s) with 150+ units — review demand`,
      });
    }
    if (pricing && pricing.win_rate < 60 && pricing.total_products > 0) {
      list.push({
        type: "critical",
        message: "Buy Box Win Rate Low",
        detail: `Only ${pricing.win_rate}% — ${pricing.losing_items.length} products losing buy box`,
      });
    }
    if (pricing) {
      const bigGap = pricing.losing_items.filter((i) => i.gap > 50);
      if (bigGap.length > 0) {
        list.push({
          type: "warning",
          message: "Large Price Gap Detected",
          detail: `${bigGap.length} product(s) priced ₹50+ above buy box price`,
        });
      }
    }
    return list;
  }, [inventory, pricing]);

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold">Dashboard</h2>
          <p className="text-sm text-muted-foreground">Overview of your seller performance</p>
        </div>
        <div className="flex items-center gap-3">
          {seedResult && (
            <span className="flex items-center gap-1 text-sm text-green-600">
              <CheckCircle2 className="h-4 w-4" />
              {seedResult}
            </span>
          )}
          {isSeeded ? (
            <Button variant="destructive" size="sm" onClick={handleUnseedDemo} disabled={unseeding}>
              {unseeding ? (
                <><Loader2 className="mr-2 h-4 w-4 animate-spin" />Removing...</>
              ) : (
                <><Trash2 className="mr-2 h-4 w-4" />Remove Demo Data</>
              )}
            </Button>
          ) : (
            <Button variant="outline" size="sm" onClick={handleSeedDemo} disabled={seeding}>
              {seeding ? (
                <><Loader2 className="mr-2 h-4 w-4 animate-spin" />Seeding...</>
              ) : (
                <><Database className="mr-2 h-4 w-4" />Seed Demo Data</>
              )}
            </Button>
          )}
        </div>
      </div>

      {loading ? (
        <div className="flex items-center justify-center py-20">
          <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
        </div>
      ) : (
        <>
          {/* Row 1: KPI Cards */}
          <div className="grid grid-cols-2 gap-4 md:grid-cols-3 lg:grid-cols-6">
            {kpis.map((kpi, i) => (
              <KPICard key={kpi.title} {...kpi} icon={KPI_ICONS[i] || TrendingUp} />
            ))}
          </div>

          {/* Row 2: Charts */}
          <div className="grid gap-6 lg:grid-cols-3">
            {/* Sales Trend */}
            <Card className="p-6 lg:col-span-2">
              <h3 className="mb-4 font-semibold">Sales Trend (Last 30 Days)</h3>
              {salesTrend.length > 0 ? (
                <ResponsiveContainer width="100%" height={250}>
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
                    <YAxis
                      tick={{ fontSize: 11 }}
                      tickFormatter={(v) => `₹${(v / 1000).toFixed(0)}k`}
                    />
                    <Tooltip formatter={(value) => [fmtINR(Number(value)), "GMV"]} />
                    <Line type="monotone" dataKey="gmv" stroke="#F97316" strokeWidth={2} dot={false} />
                  </LineChart>
                </ResponsiveContainer>
              ) : (
                <p className="py-10 text-center text-muted-foreground text-sm">No sales data yet. Seed demo data to see charts.</p>
              )}
            </Card>

            {/* Order Status Donut */}
            <Card className="p-6">
              <h3 className="mb-4 font-semibold">Order Status</h3>
              {orderStatus.length > 0 ? (
                <ResponsiveContainer width="100%" height={250}>
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
                    <Legend
                      formatter={(value: string, entry: any) => (
                        <span className="text-xs">{value} ({entry.payload.count})</span>
                      )}
                    />
                  </PieChart>
                </ResponsiveContainer>
              ) : (
                <p className="py-10 text-center text-muted-foreground text-sm">No order data yet.</p>
              )}
            </Card>
          </div>

          {/* Row 3: Products + Inventory */}
          <div className="grid gap-6 lg:grid-cols-2">
            {/* Top Products */}
            <Card className="p-6">
              <h3 className="mb-4 font-semibold">Top Products by Revenue</h3>
              {topProducts.length > 0 ? (
                <div className="overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="border-b text-left text-muted-foreground">
                        <th className="pb-2 pr-4">Product</th>
                        <th className="pb-2 pr-4 text-right">Revenue</th>
                        <th className="pb-2 text-right">Units</th>
                      </tr>
                    </thead>
                    <tbody>
                      {topProducts.map((p) => (
                        <tr key={p.asin} className="border-b last:border-0">
                          <td className="py-2 pr-4">
                            <div className="font-medium truncate max-w-[250px]">{p.title}</div>
                            <div className="text-xs text-muted-foreground">{p.asin}</div>
                          </td>
                          <td className="py-2 pr-4 text-right font-medium">{fmtINR(p.revenue)}</td>
                          <td className="py-2 text-right">{p.units_sold}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              ) : (
                <p className="py-10 text-center text-muted-foreground text-sm">No product data yet.</p>
              )}
            </Card>

            {/* Inventory Health */}
            <Card className="p-6">
              <h3 className="mb-4 font-semibold">Inventory Health</h3>
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
                            <span className="truncate max-w-[200px]">{item.seller_sku}</span>
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

          {/* Row 4: Pricing + Alerts */}
          <div className="grid gap-6 lg:grid-cols-2">
            {/* Pricing / Buy Box */}
            <Card className="p-6">
              <h3 className="mb-4 font-semibold">Buy Box Performance</h3>
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
                        <ArrowDown className="h-4 w-4" /> Not Winning Buy Box
                      </h4>
                      <div className="overflow-x-auto">
                        <table className="w-full text-sm">
                          <thead>
                            <tr className="border-b text-left text-muted-foreground">
                              <th className="pb-2 pr-4">ASIN</th>
                              <th className="pb-2 pr-4 text-right">Your Price</th>
                              <th className="pb-2 pr-4 text-right">Buy Box</th>
                              <th className="pb-2 text-right">Gap</th>
                            </tr>
                          </thead>
                          <tbody>
                            {pricing.losing_items.slice(0, 5).map((item) => (
                              <tr key={item.asin} className="border-b last:border-0">
                                <td className="py-2 pr-4 font-mono text-xs">{item.asin}</td>
                                <td className="py-2 pr-4 text-right">{fmtINR(item.your_price)}</td>
                                <td className="py-2 pr-4 text-right">{fmtINR(item.buybox_price)}</td>
                                <td className="py-2 text-right text-red-600">+₹{item.gap}</td>
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

            {/* Alerts */}
            <Card className="p-6">
              <div className="mb-4 flex items-center justify-between">
                <h3 className="font-semibold">Alerts & Recommendations</h3>
                {alerts.length > 0 && (
                  <Badge variant={alerts.some((a) => a.type === "critical") ? "destructive" : "secondary"}>
                    {alerts.length} Alert{alerts.length !== 1 && "s"}
                  </Badge>
                )}
              </div>
              {alerts.length > 0 ? (
                <div className="space-y-3">
                  {alerts.map((alert, i) => (
                    <div key={i} className="flex items-center gap-3 rounded-lg border p-3">
                      <AlertCircle className={`h-5 w-5 ${alert.type === "critical" ? "text-red-500" : "text-amber-500"}`} />
                      <div>
                        <div className="text-sm font-medium">{alert.message}</div>
                        <div className="text-xs text-muted-foreground">{alert.detail}</div>
                      </div>
                    </div>
                  ))}
                </div>
              ) : (
                <div className="flex flex-col items-center py-8 text-center">
                  <CheckCircle2 className="mb-2 h-8 w-8 text-green-500" />
                  <p className="text-sm text-muted-foreground">All clear! No alerts right now.</p>
                </div>
              )}
            </Card>
          </div>
        </>
      )}
    </div>
  );
}
