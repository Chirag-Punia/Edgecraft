import { Check } from "lucide-react";
import { cn } from "@/lib/utils";

interface StepperProps {
  currentStep: number;
  steps: string[];
}

export function Stepper({ currentStep, steps }: StepperProps) {
  return (
    <div className="mb-8 flex items-center justify-center gap-4">
      {steps.map((label, index) => {
        const step = index + 1;
        const isCompleted = step < currentStep;
        const isCurrent = step === currentStep;

        return (
          <div key={step} className="flex items-center gap-2">
            {index > 0 && (
              <div className={cn("h-px w-16", isCompleted ? "bg-orange-500" : "bg-gray-200")} />
            )}
            <div className="flex items-center gap-2">
              <div
                className={cn(
                  "flex h-8 w-8 items-center justify-center rounded-full text-sm font-medium",
                  isCompleted && "bg-green-500 text-white",
                  isCurrent && "bg-orange-500 text-white",
                  !isCompleted && !isCurrent && "bg-gray-100 text-gray-400"
                )}
              >
                {isCompleted ? <Check className="h-4 w-4" /> : step}
              </div>
              <span className={cn("text-sm", isCurrent ? "font-medium" : "text-muted-foreground")}>
                {label}
              </span>
            </div>
          </div>
        );
      })}
    </div>
  );
}
