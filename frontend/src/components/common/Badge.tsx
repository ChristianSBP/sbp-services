/* Badge-Komponente fuer Status und Formationen */

import { FORMATION_COLORS, STATUS_COLORS } from "../../types";
import type { EventStatus } from "../../types";

interface BadgeProps {
  label: string;
  variant?: "status" | "formation" | "severity";
  value?: string;
}

export default function Badge({ label, variant = "status", value }: BadgeProps) {
  let bgColor = "#6E6E73";

  if (variant === "formation" && value) {
    bgColor = FORMATION_COLORS[value] || "#6E6E73";
  } else if (variant === "status" && value) {
    bgColor = STATUS_COLORS[value as EventStatus] || "#6E6E73";
  } else if (variant === "severity") {
    switch (value) {
      case "ERROR": bgColor = "#FF3B30"; break;
      case "WARNING": bgColor = "#FF9F0A"; break;
      case "INFO": bgColor = "#0071E3"; break;
    }
  }

  return (
    <span
      className="inline-flex items-center px-2 py-0.5 text-xs font-medium rounded-full text-white"
      style={{ backgroundColor: bgColor }}
    >
      {label}
    </span>
  );
}
