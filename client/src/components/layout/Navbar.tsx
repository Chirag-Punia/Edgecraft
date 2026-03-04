import { Link } from "react-router-dom";
import { Button } from "@/components/ui/button";

export function Navbar() {
  return (
    <header className="sticky top-0 z-50 border-b bg-white/80 backdrop-blur">
      <div className="mx-auto flex h-16 max-w-7xl items-center justify-between px-4">
        <Link to="/" className="flex items-center gap-2">
          <img src="/abc.png" alt="RetailSutra" className="h-9 w-9 rounded-lg object-contain" />
          <span className="text-lg font-bold">RetailSutra</span>
        </Link>
        <div className="flex items-center gap-3">
          <Button variant="ghost" asChild>
            <Link to="/login">Login</Link>
          </Button>
          <Button className="btn-gradient rounded-lg" asChild>
            <Link to="/signup">Get Started</Link>
          </Button>
        </div>
      </div>
    </header>
  );
}
