import { Outlet, Link } from "react-router-dom";

export function OnboardingLayout() {
  return (
    <div className="flex min-h-screen flex-col bg-gradient-to-b from-orange-50/50 to-white">
      <header className="border-b bg-white/80 backdrop-blur">
        <div className="mx-auto flex h-16 max-w-7xl items-center px-4">
          <Link to="/" className="flex items-center gap-2">
            <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-gradient-to-br from-orange-500 to-pink-500">
              <span className="text-lg font-bold text-white">✦</span>
            </div>
            <span className="text-lg font-bold">Bharat Seller OS</span>
          </Link>
        </div>
      </header>
      <main className="flex flex-1 flex-col items-center px-4 py-8">
        <Outlet />
      </main>
    </div>
  );
}
