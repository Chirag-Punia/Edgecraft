import { useState, useEffect } from "react";
import { useNavigate, useSearchParams, useLocation } from "react-router-dom";
import { useAuth } from "@/hooks/useAuth";
import api from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Stepper } from "@/components/onboarding/Stepper";
import { Store, ExternalLink, CheckCircle2, AlertCircle } from "lucide-react";
import { MARKETPLACES } from "@/lib/constants";

const MARKETPLACE_ICONS: Record<string, string> = {
  amazon: "🛒",
  flipkart: "📦",
  shopify: "🛍️",
  facebook: "📱",
};

export function ConnectMarketplacesPage() {
  const navigate = useNavigate();
  const location = useLocation();
  const [searchParams, setSearchParams] = useSearchParams();
  const { refreshUser } = useAuth();
  const isDashboard = location.pathname.startsWith("/dashboard");
  const [connecting, setConnecting] = useState<string | null>(null);
  const [connected, setConnected] = useState<Set<string>>(new Set());
  const [oauthStatus, setOauthStatus] = useState<{ type: "success" | "error"; message: string } | null>(null);

  // Handle OAuth callback query params (?amazon=success or ?amazon=error&message=...)
  useEffect(() => {
    const amazonResult = searchParams.get("amazon");
    if (amazonResult === "success") {
      setOauthStatus({ type: "success", message: "Amazon account connected successfully!" });
      setConnected((prev) => new Set(prev).add("amazon"));
      setSearchParams({}, { replace: true });
    } else if (amazonResult === "error") {
      const msg = searchParams.get("message") || "Failed to connect Amazon account";
      setOauthStatus({ type: "error", message: msg });
      setSearchParams({}, { replace: true });
    }
  }, [searchParams, setSearchParams]);

  // Load already-connected marketplaces on mount
  useEffect(() => {
    api.get("/marketplaces").then(({ data }) => {
      const ids = new Set<string>(data.map((mp: { marketplace: string }) => mp.marketplace));
      setConnected(ids);
    }).catch(() => {});
  }, []);

  const handleConnect = async (marketplaceId: string) => {
    // Amazon uses OAuth redirect flow
    if (marketplaceId === "amazon") {
      setConnecting("amazon");
      try {
        const { data } = await api.get("/amazon/authorize-url");
        window.location.href = data.authorize_url;
      } catch {
        setOauthStatus({ type: "error", message: "Failed to generate Amazon authorization URL" });
        setConnecting(null);
      }
      return;
    }

    // Other marketplaces use direct connect (placeholder)
    setConnecting(marketplaceId);
    try {
      await api.post("/marketplaces", { marketplace: marketplaceId });
      setConnected((prev) => new Set(prev).add(marketplaceId));
    } catch {
      // Silently handle — may already be connected
    } finally {
      setConnecting(null);
    }
  };

  const handleContinue = async () => {
    await refreshUser();
    navigate("/dashboard");
  };

  return (
    <div className={isDashboard ? "w-full" : "w-full max-w-2xl"}>
      {!isDashboard && <Stepper currentStep={2} steps={["Business Info", "Connect Marketplaces"]} />}

      <Card className="border-0 shadow-lg">
        <CardHeader className="text-center">
          <div className="mx-auto mb-2 flex h-14 w-14 items-center justify-center rounded-xl bg-orange-100">
            <Store className="h-7 w-7 text-orange-600" />
          </div>
          <CardTitle className="text-2xl">Connect Your Marketplaces</CardTitle>
          <CardDescription>
            Connect at least one marketplace to get started. You can add more later.
          </CardDescription>
        </CardHeader>
        <CardContent>
          {oauthStatus && (
            <div
              className={`mb-4 flex items-center gap-2 rounded-lg p-3 text-sm ${
                oauthStatus.type === "success"
                  ? "bg-green-50 text-green-700 border border-green-200"
                  : "bg-red-50 text-red-700 border border-red-200"
              }`}
            >
              {oauthStatus.type === "success" ? (
                <CheckCircle2 className="h-4 w-4 shrink-0" />
              ) : (
                <AlertCircle className="h-4 w-4 shrink-0" />
              )}
              {oauthStatus.message}
            </div>
          )}
          <div className="grid grid-cols-2 gap-4 mb-6">
            {MARKETPLACES.map((mp) => {
              const isAvailable = mp.id === "amazon";
              return (
                <div
                  key={mp.id}
                  className={`relative rounded-lg border p-4 transition-colors ${
                    connected.has(mp.id)
                      ? "border-green-300 bg-green-50"
                      : isAvailable
                        ? "hover:border-orange-200"
                        : "opacity-50 cursor-not-allowed"
                  }`}
                >
                  {!isAvailable && (
                    <span className="absolute top-2 right-2 rounded-full bg-muted px-2 py-0.5 text-[10px] font-medium text-muted-foreground">
                      Coming Soon
                    </span>
                  )}
                  <div className="mb-3 flex items-center gap-2">
                    <span className="text-2xl">{MARKETPLACE_ICONS[mp.id]}</span>
                    <div>
                      <div className="font-medium">{mp.name}</div>
                      <div className="text-xs text-muted-foreground">{mp.description}</div>
                    </div>
                  </div>
                  <Button
                    variant={connected.has(mp.id) ? "secondary" : "outline"}
                    size="sm"
                    className="w-full gap-2"
                    disabled={!isAvailable || connecting === mp.id || connected.has(mp.id)}
                    onClick={() => handleConnect(mp.id)}
                  >
                    {connected.has(mp.id) ? (
                      "Connected"
                    ) : !isAvailable ? (
                      "Coming Soon"
                    ) : connecting === mp.id ? (
                      "Connecting..."
                    ) : (
                      <>
                        <ExternalLink className="h-3 w-3" />
                        Connect with {mp.name}
                      </>
                    )}
                  </Button>
                </div>
              );
            })}
          </div>

          {!isDashboard && (
            <>
              <div className="flex gap-4">
                <Button
                  variant="outline"
                  className="flex-1"
                  onClick={() => navigate("/onboarding/business-info")}
                >
                  Back
                </Button>
                <Button className="btn-gradient flex-1" onClick={handleContinue}>
                  {connected.size > 0 ? "Continue to Dashboard" : "Skip for Now"}
                </Button>
              </div>
              <p className="mt-3 text-center text-xs text-muted-foreground">
                You can connect marketplaces later from Settings
              </p>
            </>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
