import { useState, useEffect, useCallback, useRef } from "react";
import api from "@/lib/api";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { InfoTip } from "@/components/dashboard/InfoTip";
import {
  Sparkles,
  ArrowLeft,
  RefreshCw,
  Loader2,
  HeartPulse,
  Grid2x2,
  CircleDollarSign,
  Newspaper,
  BadgePercent,
  Clock,
  AlertTriangle,
} from "lucide-react";

// ── Types ──────────────────────────────────

interface ReportSummary {
  report_type: string;
  title: string;
  description: string;
  generated_at: string | null;
  is_stale: boolean;
  status: string;
}

interface ReportDetail {
  report_type: string;
  title: string;
  ai_narrative: string;
  report_data: Record<string, any> | null;
  score: number | null;
  generated_at: string | null;
  status: string;
}

// ── Constants ──────────────────────────────

const REPORT_ICONS: Record<string, typeof Sparkles> = {
  business_health: HeartPulse,
  product_matrix: Grid2x2,
  revenue_leakage: CircleDollarSign,
  weekly_digest: Newspaper,
  pricing_strategy: BadgePercent,
};

const REPORT_COLORS: Record<string, string> = {
  business_health: "from-emerald-500/10 to-teal-500/10 border-emerald-200",
  product_matrix: "from-violet-500/10 to-purple-500/10 border-violet-200",
  revenue_leakage: "from-red-500/10 to-rose-500/10 border-red-200",
  weekly_digest: "from-blue-500/10 to-cyan-500/10 border-blue-200",
  pricing_strategy: "from-amber-500/10 to-yellow-500/10 border-amber-200",
};

const ICON_COLORS: Record<string, string> = {
  business_health: "text-emerald-600",
  product_matrix: "text-violet-600",
  revenue_leakage: "text-red-600",
  weekly_digest: "text-blue-600",
  pricing_strategy: "text-amber-600",
};

const REPORT_INFO_TIPS: Record<string, string> = {
  business_health:
    "Generated from: 7-day revenue trends, cancellation rates, inventory levels (low stock SKUs), buy box win rates, customer sentiment scores, and stockout risk forecasts.",
  product_matrix:
    "Generated from: Per-product 30-day revenue, units sold, current stock levels, buy box status, review sentiment, and stockout risk.",
  revenue_leakage:
    "Generated from: 30-day cancellation revenue, buy box pricing gaps (your price vs. winning price), and stockout risk forecasts with predicted demand.",
  weekly_digest:
    "Generated from: Week-over-week revenue and order trends, top products by weekly revenue, cancellation rate, buy box performance, stock alerts, and sentiment.",
  pricing_strategy:
    "Generated from: Current pricing vs. buy box and lowest prices, buy box win/loss status, customer sentiment scores, and 30-day revenue per product.",
};

function timeAgo(dateStr: string): string {
  // Backend stores naive UTC — append Z so JS parses as UTC, not local time
  const utc = dateStr.endsWith("Z") ? dateStr : dateStr + "Z";
  const diff = Date.now() - new Date(utc).getTime();
  const mins = Math.floor(diff / 60000);
  if (mins < 1) return "just now";
  if (mins < 60) return `${mins}m ago`;
  const hours = Math.floor(mins / 60);
  if (hours < 24) return `${hours}h ago`;
  return `${Math.floor(hours / 24)}d ago`;
}

// ── Score Gauge ────────────────────────────

function ScoreGauge({ score }: { score: number }) {
  const color = score >= 70 ? "text-emerald-600" : score >= 40 ? "text-amber-600" : "text-red-600";
  const bgColor = score >= 70 ? "stroke-emerald-500" : score >= 40 ? "stroke-amber-500" : "stroke-red-500";
  const circumference = 2 * Math.PI * 54;
  const dashOffset = circumference * (1 - score / 100);

  return (
    <div className="flex flex-col items-center">
      <svg width="140" height="140" viewBox="0 0 120 120">
        <circle cx="60" cy="60" r="54" fill="none" stroke="#e5e7eb" strokeWidth="8" />
        <circle
          cx="60" cy="60" r="54" fill="none" className={bgColor} strokeWidth="8"
          strokeLinecap="round" strokeDasharray={circumference} strokeDashoffset={dashOffset}
          transform="rotate(-90 60 60)"
        />
        <text x="60" y="55" textAnchor="middle" className={`text-3xl font-bold fill-current ${color}`}>
          {score}
        </text>
        <text x="60" y="75" textAnchor="middle" className="text-xs fill-muted-foreground">/100</text>
      </svg>
    </div>
  );
}

// ── Dimension Bars (for health scorecard) ──

function DimensionBars({ dimensions }: { dimensions: Record<string, number> }) {
  const labels: Record<string, string> = {
    sales: "Sales Momentum",
    inventory: "Inventory Health",
    pricing: "Pricing Competitiveness",
    satisfaction: "Customer Satisfaction",
    demand: "Demand Outlook",
  };
  return (
    <div className="space-y-2">
      {Object.entries(dimensions).map(([key, value]) => (
        <div key={key}>
          <div className="flex justify-between text-xs mb-0.5">
            <span className="text-muted-foreground">{labels[key] || key}</span>
            <span className="font-medium">{value}/100</span>
          </div>
          <div className="h-2 rounded-full bg-muted overflow-hidden">
            <div
              className={`h-full rounded-full transition-all ${
                value >= 70 ? "bg-emerald-500" : value >= 40 ? "bg-amber-500" : "bg-red-500"
              }`}
              style={{ width: `${value}%` }}
            />
          </div>
        </div>
      ))}
    </div>
  );
}

// ── Product Matrix Pills ───────────────────

const QUADRANT_STYLES: Record<string, { label: string; color: string }> = {
  star: { label: "Star", color: "bg-emerald-100 text-emerald-700" },
  cash_cow_at_risk: { label: "At Risk", color: "bg-red-100 text-red-700" },
  hidden_gem: { label: "Hidden Gem", color: "bg-blue-100 text-blue-700" },
  problem_child: { label: "Problem", color: "bg-gray-100 text-gray-700" },
};

function ProductMatrix({ products }: { products: { name: string; quadrant: string; action: string }[] }) {
  return (
    <div className="space-y-2">
      {products.map((p, i) => {
        const style = QUADRANT_STYLES[p.quadrant] || QUADRANT_STYLES.problem_child;
        return (
          <div key={i} className="flex items-start gap-3 rounded-lg border p-3">
            <Badge className={`shrink-0 text-[10px] ${style.color}`}>{style.label}</Badge>
            <div className="min-w-0">
              <div className="text-sm font-medium truncate">{p.name}</div>
              <div className="text-xs text-muted-foreground">{p.action}</div>
            </div>
          </div>
        );
      })}
    </div>
  );
}

// ── Main Component ─────────────────────────

export function AIReportsPage() {
  const [reports, setReports] = useState<ReportSummary[]>([]);
  const [selected, setSelected] = useState<string | null>(null);
  const [detail, setDetail] = useState<ReportDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [generating, setGenerating] = useState(false);
  const [refreshing, setRefreshing] = useState(false);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  // Cleanup polling on unmount
  useEffect(() => {
    return () => { if (pollRef.current) clearInterval(pollRef.current); };
  }, []);

  const fetchList = useCallback(() => {
    setLoading(true);
    api.get("/ai-reports/").then(({ data }) => {
      setReports(data.reports);
      setLoading(false);
    }).catch(() => setLoading(false));
  }, []);

  useEffect(() => { fetchList(); }, [fetchList]);

  const openReport = async (type: string) => {
    setSelected(type);
    setDetail(null);
    setGenerating(true);
    try {
      const { data } = await api.get(`/ai-reports/${type}`);
      if (data.status === "generating") {
        // Poll until ready (max 30 seconds)
        let attempts = 0;
        if (pollRef.current) clearInterval(pollRef.current);
        pollRef.current = setInterval(async () => {
          attempts++;
          try {
            const { data: updated } = await api.get(`/ai-reports/${type}`);
            if (updated.status !== "generating" || attempts >= 10) {
              clearInterval(pollRef.current!);
              pollRef.current = null;
              setDetail(updated);
              setGenerating(false);
            }
          } catch {
            clearInterval(pollRef.current!);
            pollRef.current = null;
            setGenerating(false);
          }
        }, 3000);
      } else {
        setDetail(data);
        setGenerating(false);
      }
    } catch {
      setDetail({
        report_type: type, title: "Error", ai_narrative: "Failed to load report.",
        report_data: null, score: null, generated_at: null, status: "failed",
      });
      setGenerating(false);
    }
  };

  const [refreshError, setRefreshError] = useState<string | null>(null);

  const handleRefresh = async () => {
    if (!selected) return;
    setRefreshing(true);
    setRefreshError(null);
    try {
      const { data } = await api.post(`/ai-reports/${selected}/refresh`);
      setDetail(data);
      fetchList();
    } catch (err: any) {
      if (err?.response?.status === 429) {
        setRefreshError("Please wait 5 minutes between refreshes.");
      }
    } finally {
      setRefreshing(false);
    }
  };

  const handleBack = () => {
    if (pollRef.current) { clearInterval(pollRef.current); pollRef.current = null; }
    setSelected(null);
    setDetail(null);
    setGenerating(false);
    fetchList();
  };

  // ── Gallery View ──
  if (!selected) {
    return (
      <div className="space-y-6">
        <div>
          <h2 className="text-2xl font-bold flex items-center gap-2">
            <Sparkles className="h-6 w-6 text-primary" />
            AI Reports
          </h2>
          <p className="text-sm text-muted-foreground mt-1">
            Cross-domain insights powered by AI — not just numbers, but what they mean for your business.
          </p>
        </div>

        {loading ? (
          <div className="flex items-center justify-center py-20">
            <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
          </div>
        ) : (
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {reports.map((r, idx) => {
              const Icon = REPORT_ICONS[r.report_type] || Sparkles;
              const gradient = REPORT_COLORS[r.report_type] || "from-gray-500/10 to-gray-500/10";
              const iconColor = ICON_COLORS[r.report_type] || "text-gray-600";
              const staggerDelays = ["", "delay-75", "delay-150", "delay-225", "delay-300"];
              return (
                <Card
                  key={r.report_type}
                  className={`group cursor-pointer border bg-gradient-to-br ${gradient} p-5 transition-all hover:shadow-md hover:-translate-y-0.5 animate-slide-up ${staggerDelays[idx] || ""}`}
                  onClick={() => openReport(r.report_type)}
                >
                  <div className="flex items-start justify-between mb-3">
                    <div className={`rounded-lg bg-background p-2.5 shadow-sm ${iconColor}`}>
                      <Icon className="h-5 w-5" />
                    </div>
                    {r.status === "ready" && !r.is_stale ? (
                      <Badge variant="secondary" className="text-[10px]">Ready</Badge>
                    ) : r.status === "generating" ? (
                      <Badge className="text-[10px] bg-primary/10 text-primary">Generating...</Badge>
                    ) : (
                      <Badge variant="outline" className="text-[10px]">New</Badge>
                    )}
                  </div>
                  <h3 className="font-semibold text-sm mb-1 flex items-center gap-1.5">
                    {r.title}
                    {REPORT_INFO_TIPS[r.report_type] && <InfoTip text={REPORT_INFO_TIPS[r.report_type]} />}
                  </h3>
                  <p className="text-xs text-muted-foreground line-clamp-2">{r.description}</p>
                  {r.generated_at && (
                    <div className="flex items-center gap-1 mt-3 text-[10px] text-muted-foreground">
                      <Clock className="h-3 w-3" />
                      Updated {timeAgo(r.generated_at)}
                    </div>
                  )}
                </Card>
              );
            })}
          </div>
        )}
      </div>
    );
  }

  // ── Detail View ──
  const config = reports.find((r) => r.report_type === selected);
  const Icon = REPORT_ICONS[selected] || Sparkles;
  const iconColor = ICON_COLORS[selected] || "text-gray-600";

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Button variant="ghost" size="sm" onClick={handleBack}>
            <ArrowLeft className="h-4 w-4 mr-1" /> Back
          </Button>
          <div className={`rounded-lg bg-background p-2 shadow-sm ${iconColor}`}>
            <Icon className="h-5 w-5" />
          </div>
          <div>
            <h2 className="text-lg font-bold flex items-center gap-1.5">
              {config?.title || selected}
              {REPORT_INFO_TIPS[selected] && <InfoTip text={REPORT_INFO_TIPS[selected]} />}
            </h2>
            {detail?.generated_at && (
              <p className="text-xs text-muted-foreground">Generated {timeAgo(detail.generated_at)}</p>
            )}
          </div>
        </div>
        <div className="flex flex-col items-end gap-1">
          <Button
            variant="outline" size="sm"
            onClick={handleRefresh}
            disabled={refreshing || generating}
          >
            {refreshing ? (
              <><Loader2 className="mr-2 h-4 w-4 animate-spin" />Refreshing...</>
            ) : (
              <><RefreshCw className="mr-2 h-4 w-4" />Refresh</>
            )}
          </Button>
          {refreshError && (
            <span className="text-[11px] text-amber-600">{refreshError}</span>
          )}
        </div>
      </div>

      {/* Content */}
      {generating ? (
        <Card className="flex flex-col items-center justify-center py-16">
          <Sparkles className="h-10 w-10 text-primary animate-pulse mb-4" />
          <p className="text-sm font-medium">AI is analyzing your data...</p>
          <p className="text-xs text-muted-foreground mt-1">Cross-referencing sales, inventory, pricing, and reviews</p>
        </Card>
      ) : detail?.status === "failed" ? (
        <Card className="flex flex-col items-center justify-center py-16">
          <AlertTriangle className="h-8 w-8 text-amber-500 mb-3" />
          <p className="text-sm">{detail.ai_narrative}</p>
          <Button variant="outline" size="sm" className="mt-4" onClick={handleRefresh}>
            Try Again
          </Button>
        </Card>
      ) : detail ? (
        <div className="grid gap-6 lg:grid-cols-3">
          {/* Structured Data Panel */}
          {detail.report_data && (
            <Card className="p-6 lg:col-span-1 order-2 lg:order-1">
              {/* Health Scorecard */}
              {selected === "business_health" && detail.score != null && (
                <div className="space-y-6">
                  <ScoreGauge score={detail.score} />
                  {detail.report_data.dimensions && (
                    <DimensionBars dimensions={detail.report_data.dimensions} />
                  )}
                  {detail.report_data.quick_win && (
                    <div className="rounded-lg bg-emerald-50 border border-emerald-200 p-3">
                      <div className="text-xs font-medium text-emerald-700 mb-1">Quick Win</div>
                      <div className="text-xs text-emerald-900">{detail.report_data.quick_win}</div>
                    </div>
                  )}
                </div>
              )}

              {/* Product Matrix */}
              {selected === "product_matrix" && detail.report_data.products?.length > 0 && detail.report_data.products[0]?.quadrant && (
                <ProductMatrix products={detail.report_data.products} />
              )}

              {/* Revenue Leakage */}
              {selected === "revenue_leakage" && detail.report_data.leakage_summary && (
                <div className="space-y-3">
                  <h4 className="text-sm font-semibold">Revenue Leakage Breakdown</h4>
                  {Object.entries(detail.report_data.leakage_summary as Record<string, number>)
                    .filter(([k]) => k !== "total")
                    .map(([key, val]) => (
                      <div key={key} className="flex justify-between items-center text-sm">
                        <span className="capitalize text-muted-foreground">{key.replace(/_/g, " ")}</span>
                        <span className="font-medium text-red-600">₹{Math.round(val).toLocaleString("en-IN")}</span>
                      </div>
                    ))}
                  <div className="border-t pt-2 flex justify-between text-sm font-bold">
                    <span>Total Leakage</span>
                    <span className="text-red-600">
                      ₹{Math.round(detail.report_data.leakage_summary.total || 0).toLocaleString("en-IN")}
                    </span>
                  </div>
                </div>
              )}

              {/* Weekly Digest */}
              {selected === "weekly_digest" && detail.report_data.action_items && (
                <div className="space-y-3">
                  <h4 className="text-sm font-semibold">This Week's Actions</h4>
                  {(detail.report_data.action_items as string[]).map((item, i) => (
                    <div key={i} className="flex gap-2 text-sm">
                      <span className="shrink-0 flex h-5 w-5 items-center justify-center rounded-full bg-primary/10 text-primary text-[10px] font-bold">
                        {i + 1}
                      </span>
                      <span className="text-muted-foreground">{item}</span>
                    </div>
                  ))}
                </div>
              )}

              {/* Pricing Strategy */}
              {selected === "pricing_strategy" && detail.report_data.recommendations?.length > 0 && detail.report_data.recommendations[0]?.action && (
                <div className="space-y-2">
                  <h4 className="text-sm font-semibold">Recommendations</h4>
                  {(detail.report_data.recommendations as { name: string; action: string; target_price: number; reasoning: string }[]).map((r, i) => (
                    <div key={i} className="rounded-lg border p-3">
                      <div className="flex items-center justify-between mb-1">
                        <span className="text-sm font-medium truncate max-w-[150px]">{r.name}</span>
                        <Badge className={`text-[10px] ${
                          r.action === "reduce" ? "bg-red-100 text-red-700" :
                          r.action === "increase" ? "bg-emerald-100 text-emerald-700" :
                          "bg-gray-100 text-gray-700"
                        }`}>{r.action}</Badge>
                      </div>
                      {r.target_price > 0 && (
                        <div className="text-xs text-muted-foreground">Target: ₹{r.target_price}</div>
                      )}
                      <div className="text-[10px] text-muted-foreground mt-1">{r.reasoning}</div>
                    </div>
                  ))}
                </div>
              )}

              {/* Fallback: show when no specific renderer matched */}
              {!(selected === "business_health" && detail.score != null) &&
               !(selected === "product_matrix" && detail.report_data.products?.[0]?.quadrant) &&
               !(selected === "revenue_leakage" && detail.report_data.leakage_summary) &&
               !(selected === "weekly_digest" && detail.report_data.action_items) &&
               !(selected === "pricing_strategy" && detail.report_data.recommendations?.[0]?.action) && (
                <div className="space-y-3">
                  <h4 className="text-sm font-semibold text-muted-foreground">Report Data</h4>
                  <pre className="text-xs text-muted-foreground whitespace-pre-wrap bg-muted rounded-lg p-3 max-h-96 overflow-y-auto leading-relaxed">
                    {JSON.stringify(detail.report_data, null, 2)}
                  </pre>
                </div>
              )}
            </Card>
          )}

          {/* AI Narrative */}
          <Card className={`p-6 ${detail.report_data ? "lg:col-span-2" : "lg:col-span-3"} order-1 lg:order-2`}>
            <div className="flex items-center gap-2 mb-4">
              <Sparkles className="h-4 w-4 text-primary" />
              <h3 className="text-sm font-semibold text-muted-foreground">AI Analysis</h3>
            </div>
            <div className="prose prose-sm max-w-none text-foreground leading-relaxed">
              {detail.ai_narrative.split("\n").map((line, i) => {
                if (!line.trim()) return <br key={i} />;
                // Safe bold rendering — split on **bold** markers, no innerHTML
                const parts = line.split(/\*\*(.*?)\*\*/g);
                return (
                  <p key={i} className="mb-2">
                    {parts.map((part, j) =>
                      j % 2 === 1 ? <strong key={j}>{part}</strong> : <span key={j}>{part}</span>
                    )}
                  </p>
                );
              })}
            </div>
          </Card>
        </div>
      ) : null}
    </div>
  );
}
