import type { RouteObject } from "react-router";

import { AppShell } from "@/components/layout/AppShell";
import { AnalysisPage } from "@/pages/AnalysisPage";
import { DashboardPage } from "@/pages/DashboardPage";
import { NotFoundPage } from "@/pages/NotFoundPage";
import { ReportsPage } from "@/pages/ReportsPage";
import { RouteErrorPage } from "@/pages/RouteErrorPage";
import { SettingsPage } from "@/pages/SettingsPage";
import { StatementsPage } from "@/pages/StatementsPage";

export const routes: RouteObject[] = [
  {
    element: <AppShell />,
    errorElement: <RouteErrorPage />,
    children: [
      { index: true, element: <DashboardPage /> },
      { path: "statements", element: <StatementsPage /> },
      { path: "analysis", element: <AnalysisPage /> },
      { path: "reports", element: <ReportsPage /> },
      { path: "settings", element: <SettingsPage /> },
      { path: "*", element: <NotFoundPage /> },
    ],
  },
];
