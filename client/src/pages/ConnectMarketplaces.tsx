import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "@/hooks/useAuth";
import api from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Stepper } from "@/components/onboarding/Stepper";
import { Store, ExternalLink } from "lucide-react";
import { MARKETPLACES } from "@/lib/constants";

const MARKETPLACE_ICONS: Record<string, string> = {
  amazon: "🛒",
  flipkart: "📦",
  shopify: "🛍️",
  facebook: "📱",
};

export function ConnectMarketplacesPage() {
  const navigate = useNavigate();
  const { refreshUser } = useAuth();
  const [connecting, setConnecting] = useState<string | null>(null);
  const [connected, setConnected] = useState<Set<string>>(new Set());

  const handleConnect = async (marketplaceId: string) => {
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
    <div className="w-full max-w-2xl">
      <Stepper currentStep={2} steps={["Business Info", "Connect Marketplaces"]} />

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
          <div className="grid grid-cols-2 gap-4 mb-6">
            {MARKETPLACES.map((mp) => (
              <div
                key={mp.id}
                className={`rounded-lg border p-4 transition-colors ${
                  connected.has(mp.id) ? "border-green-300 bg-green-50" : "hover:border-orange-200"
                }`}
              >
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
                  disabled={connecting === mp.id || connected.has(mp.id)}
                  onClick={() => handleConnect(mp.id)}
                >
                  {connected.has(mp.id) ? (
                    "Connected"
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
            ))}
          </div>

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
        </CardContent>
      </Card>
    </div>
  );
}
