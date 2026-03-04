import { Routes, Route, Navigate } from "react-router-dom";
import { useAuth } from "@/hooks/useAuth";

import { AuthLayout } from "@/components/layout/AuthLayout";
import { OnboardingLayout } from "@/components/layout/OnboardingLayout";
import { DashboardLayout } from "@/components/layout/DashboardLayout";

import { LandingPage } from "@/pages/Landing";
import { LoginPage } from "@/pages/Login";
import { SignupPage } from "@/pages/Signup";
import { VerifyEmailPage } from "@/pages/VerifyEmail";
import { BusinessInfoPage } from "@/pages/BusinessInfo";
import { ConnectMarketplacesPage } from "@/pages/ConnectMarketplaces";
import { DashboardPage } from "@/pages/Dashboard";
import { PlaceholderPage } from "@/pages/placeholder/Placeholder";


function RequireAuth({ children }: { children: React.ReactNode }) {
  const { user, loading } = useAuth();
  if (loading) return <div className="flex h-screen items-center justify-center">Loading...</div>;
  if (!user) return <Navigate to="/login" replace />;
  return <>{children}</>;
}

function RequireVerified({ children }: { children: React.ReactNode }) {
  const { user, loading } = useAuth();
  if (loading) return <div className="flex h-screen items-center justify-center">Loading...</div>;
  if (!user) return <Navigate to="/login" replace />;
  if (!user.is_email_verified) return <Navigate to="/verify-email" replace />;
  return <>{children}</>;
}

function RequireOnboarded({ children }: { children: React.ReactNode }) {
  const { user, loading } = useAuth();
  if (loading) return <div className="flex h-screen items-center justify-center">Loading...</div>;
  if (!user) return <Navigate to="/login" replace />;
  if (!user.is_email_verified) return <Navigate to="/verify-email" replace />;
  if (!user.seller_id) return <Navigate to="/onboarding/business-info" replace />;
  return <>{children}</>;
}

function RedirectIfAuth({ children }: { children: React.ReactNode }) {
  const { user, loading } = useAuth();
  if (loading) return <div className="flex h-screen items-center justify-center">Loading...</div>;
  if (user && user.is_email_verified && user.seller_id) return <Navigate to="/dashboard" replace />;
  return <>{children}</>;
}

export default function App() {
  return (
    <Routes>
      {/* Public */}
      <Route path="/" element={<LandingPage />} />

      {/* Auth */}
      <Route element={<RedirectIfAuth><AuthLayout /></RedirectIfAuth>}>
        <Route path="/login" element={<LoginPage />} />
        <Route path="/signup" element={<SignupPage />} />
      </Route>

      {/* Email verification (needs auth but not verification) */}
      <Route element={<RequireAuth><AuthLayout /></RequireAuth>}>
        <Route path="/verify-email" element={<VerifyEmailPage />} />
      </Route>

      {/* Onboarding (needs verified email) */}
      <Route element={<RequireVerified><OnboardingLayout /></RequireVerified>}>
        <Route path="/onboarding/business-info" element={<BusinessInfoPage />} />
        <Route path="/onboarding/marketplaces" element={<ConnectMarketplacesPage />} />
      </Route>

      {/* Dashboard (needs full onboarding) */}
      <Route element={<RequireOnboarded><DashboardLayout /></RequireOnboarded>}>
        <Route path="/dashboard" element={<DashboardPage />} />
        <Route path="/dashboard/assistant" element={<PlaceholderPage title="AI Assistant" />} />
        <Route path="/dashboard/marketplaces" element={<ConnectMarketplacesPage />} />
        <Route path="/dashboard/settings" element={<PlaceholderPage title="Settings" />} />
      </Route>

      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
