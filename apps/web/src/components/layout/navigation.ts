import {
  ChartLine,
  FileSpreadsheet,
  FileText,
  LayoutDashboard,
  type LucideIcon,
  Settings,
} from "lucide-react";

export interface NavItem {
  to: string;
  label: string;
  icon: LucideIcon;
}

export const NAV_ITEMS: readonly NavItem[] = [
  { to: "/", label: "Dashboard", icon: LayoutDashboard },
  { to: "/statements", label: "Financial statements", icon: FileSpreadsheet },
  { to: "/analysis", label: "Analysis", icon: ChartLine },
  { to: "/reports", label: "Reports", icon: FileText },
  { to: "/settings", label: "Settings", icon: Settings },
];
