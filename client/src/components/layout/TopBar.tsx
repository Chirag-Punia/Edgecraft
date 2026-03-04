import { useAuth } from "@/hooks/useAuth";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import { ChevronDown, LogOut } from "lucide-react";
import { useNavigate } from "react-router-dom";

export function TopBar() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();

  const handleLogout = () => {
    logout();
    navigate("/login");
  };

  return (
    <header className="flex h-16 items-center justify-between border-b bg-white px-6">
      <div className="flex items-center gap-4">
        <h1 className="text-lg font-semibold">Command Center</h1>
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <Button variant="outline" size="sm" className="gap-1">
              <span className="text-xs">🛒</span>
              Amazon.in
              <ChevronDown className="h-3 w-3" />
            </Button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="start">
            <DropdownMenuItem className="font-medium">
              <span className="mr-2 text-xs">🛒</span>
              Amazon.in
            </DropdownMenuItem>
            <DropdownMenuItem disabled className="opacity-40">
              <span className="mr-2 text-xs">🛍️</span>
              Flipkart — Coming Soon
            </DropdownMenuItem>
            <DropdownMenuItem disabled className="opacity-40">
              <span className="mr-2 text-xs">🟢</span>
              Shopify — Coming Soon
            </DropdownMenuItem>
            <DropdownMenuItem disabled className="opacity-40">
              <span className="mr-2 text-xs">📘</span>
              Facebook Marketplace — Coming Soon
            </DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>
      </div>
      <div className="flex items-center gap-4">
        <span className="text-sm text-muted-foreground">English</span>
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <Button variant="ghost" size="icon" className="rounded-full">
              <Avatar className="h-8 w-8">
                <AvatarFallback className="bg-orange-100 text-orange-700 text-xs">
                  {user?.full_name?.charAt(0) || "U"}
                </AvatarFallback>
              </Avatar>
            </Button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="end">
            <DropdownMenuItem onClick={handleLogout}>
              <LogOut className="mr-2 h-4 w-4" />
              Logout
            </DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>
      </div>
    </header>
  );
}
