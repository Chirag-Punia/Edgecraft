import { Link } from "react-router-dom";
import { Navbar } from "@/components/layout/Navbar";
import { Button } from "@/components/ui/button";
import { ArrowRight, Play } from "lucide-react";

export function LandingPage() {
  return (
    <div className="min-h-screen bg-white">
      <Navbar />

      {/* Hero */}
      <section className="mx-auto max-w-7xl px-4 py-16 md:py-24">
        <div className="grid items-center gap-12 md:grid-cols-2">
          <div>
            <div className="mb-4 inline-flex items-center gap-2 rounded-full bg-primary/5 px-4 py-1.5 text-sm text-primary">
              <span>🔥</span> Trusted by 10,000+ Indian Sellers
            </div>
            <h1 className="mb-6 text-4xl font-bold leading-tight md:text-5xl">
              Manage All Your Marketplaces{" "}
              <span className="bg-gradient-to-r from-purple-600 to-blue-600 bg-clip-text text-transparent">
                From One Dashboard
              </span>
            </h1>
            <p className="mb-8 text-lg text-muted-foreground">
              Say goodbye to switching between Amazon, Flipkart, Shopify, and Facebook.
              Get AI-powered insights, real-time inventory sync, smart pricing, and
              regional language support—all in one place.
            </p>

            {/* Stats */}
            <div className="mb-8 flex gap-8">
              <div>
                <div className="text-2xl font-bold text-primary">80%</div>
                <div className="text-sm text-muted-foreground">Time Saved</div>
              </div>
              <div>
                <div className="text-2xl font-bold text-primary">35%</div>
                <div className="text-sm text-muted-foreground">Revenue Growth</div>
              </div>
              <div>
                <div className="text-2xl font-bold text-primary">24/7</div>
                <div className="text-sm text-muted-foreground">AI Support</div>
              </div>
            </div>

            {/* CTAs */}
            <div className="flex items-center gap-4">
              <Button className="btn-gradient h-12 rounded-lg px-8 text-base" asChild>
                <Link to="/signup">
                  Start Free Trial <ArrowRight className="ml-2 h-4 w-4" />
                </Link>
              </Button>
              <Button variant="ghost" className="h-12 gap-2 text-base">
                <Play className="h-4 w-4" /> Watch Demo
              </Button>
            </div>
            <p className="mt-3 text-xs text-muted-foreground">
              No credit card required · 14-day free trial · Cancel anytime
            </p>
          </div>

          {/* Hero image placeholder */}
          <div className="relative">
            <div className="overflow-hidden rounded-2xl border bg-gradient-to-br from-purple-50 to-blue-50 p-8 shadow-lg">
              <div className="flex items-center justify-between mb-4">
                <div className="flex items-center gap-2">
                  <div className="h-3 w-3 rounded-full bg-green-400" />
                  <span className="text-sm font-medium text-green-600">Live Sync</span>
                </div>
              </div>
              <div className="space-y-3">
                <div className="h-8 rounded bg-white/80 shadow-sm" />
                <div className="grid grid-cols-3 gap-3">
                  <div className="h-20 rounded bg-white/80 shadow-sm" />
                  <div className="h-20 rounded bg-white/80 shadow-sm" />
                  <div className="h-20 rounded bg-white/80 shadow-sm" />
                </div>
                <div className="h-32 rounded bg-white/80 shadow-sm" />
              </div>
              <div className="mt-4 inline-flex items-center gap-1 rounded-full bg-white/80 px-3 py-1 text-xs shadow-sm">
                🌐 5 Languages
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* Footer */}
      <footer className="border-t bg-gray-50 py-8">
        <div className="mx-auto max-w-7xl px-4 text-center text-sm text-muted-foreground">
          © 2026 RetailSutra. All rights reserved.
        </div>
      </footer>
    </div>
  );
}
