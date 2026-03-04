import { Card } from "@/components/ui/card";
import { Construction } from "lucide-react";

interface PlaceholderPageProps {
  title: string;
}

export function PlaceholderPage({ title }: PlaceholderPageProps) {
  return (
    <div className="flex flex-1 items-center justify-center">
      <Card className="max-w-md p-8 text-center">
        <Construction className="mx-auto mb-4 h-12 w-12 text-orange-400" />
        <h2 className="mb-2 text-xl font-semibold">{title}</h2>
        <p className="text-muted-foreground">
          This section is coming soon. We're building something amazing for you!
        </p>
      </Card>
    </div>
  );
}
