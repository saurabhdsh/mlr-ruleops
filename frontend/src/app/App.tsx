import { Navigate, Route, Routes } from "react-router-dom";
import { AppLayout } from "../layouts/AppLayout";
import { LoginPage } from "../pages/Login";
import { CommandCenter } from "../pages/CommandCenter";
import { TicketsPage } from "../pages/Tickets";
import { WorkspacePage } from "../pages/Workspace";
import { RuleExplorer } from "../pages/RuleExplorer";
import { TestingLab } from "../pages/TestingLab";
import { ApprovalsPage } from "../pages/Approvals";
import { DeploymentsPage } from "../pages/Deployments";
import { VersionsPage } from "../pages/Versions";
import { AuditPage } from "../pages/Audit";
import { AnalyticsPage } from "../pages/Analytics";
import { AdminPage } from "../pages/Admin";
import { getToken } from "../api/client";

function Guard({ children }: { children: React.ReactNode }) {
  if (!getToken()) return <Navigate to="/login" replace />;
  return <>{children}</>;
}

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route
        element={
          <Guard>
            <AppLayout />
          </Guard>
        }
      >
        <Route path="/" element={<CommandCenter />} />
        <Route path="/tickets" element={<TicketsPage />} />
        <Route path="/tickets/:id" element={<WorkspacePage />} />
        <Route path="/workspace" element={<WorkspacePage />} />
        <Route path="/rules" element={<RuleExplorer />} />
        <Route path="/testing" element={<TestingLab />} />
        <Route path="/approvals" element={<ApprovalsPage />} />
        <Route path="/deployments" element={<DeploymentsPage />} />
        <Route path="/versions" element={<VersionsPage />} />
        <Route path="/audit" element={<AuditPage />} />
        <Route path="/analytics" element={<AnalyticsPage />} />
        <Route path="/admin" element={<AdminPage />} />
      </Route>
    </Routes>
  );
}
