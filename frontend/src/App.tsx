import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import BrowseMarketplaces from "./pages/BrowseMarketplaces";
import BrowseMarketplaceDetail from "./pages/BrowseMarketplaceDetail";
import NewMarketplace from "./pages/NewMarketplace";
import MarketplaceDetail from "./pages/MarketplaceDetail";
import PluginEditor from "./pages/PluginEditor";
import ComponentEditor from "./pages/ComponentEditor";
import OrganizationAdmin from "./pages/OrganizationAdmin";
import Login from "./pages/Login";
import ChangePassword from "./pages/ChangePassword";
import SetupWizard from "./pages/SetupWizard";
import { AuthProvider } from "./lib/auth";
import AuthGate from "./components/AuthGate";
import ManageGate from "./components/ManageGate";
import AppShell from "./components/AppShell";

export default function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <Routes>
          <Route path="/setup" element={<AuthGate><SetupWizard /></AuthGate>} />
          <Route path="/login" element={<AuthGate><Login /></AuthGate>} />
          <Route path="/change-password" element={<AuthGate><ChangePassword /></AuthGate>} />

          <Route element={<AuthGate><AppShell /></AuthGate>}>
            {/* Consumer browsing */}
            <Route path="/" element={<BrowseMarketplaces />} />
            <Route path="/marketplaces/:slug" element={<BrowseMarketplaceDetail />} />

            {/* Organization admin */}
            <Route path="/organization" element={<OrganizationAdmin />} />
            <Route path="/organization/auth" element={<OrganizationAdmin />} />
            <Route path="/organization/access" element={<OrganizationAdmin />} />
            <Route path="/organization/tokens" element={<OrganizationAdmin />} />
            <Route path="/organization/users" element={<OrganizationAdmin />} />

            {/* Marketplace management — requires authenticated org/marketplace admin */}
            <Route path="/manage" element={<Navigate to="/" replace />} />
            <Route path="/manage/marketplaces/new" element={<ManageGate><NewMarketplace /></ManageGate>} />
            <Route path="/manage/marketplaces/:slug" element={<ManageGate><MarketplaceDetail /></ManageGate>} />
            <Route path="/manage/marketplaces/:slug/plugins/new" element={<ManageGate><PluginEditor /></ManageGate>} />
            <Route path="/manage/marketplaces/:slug/plugins/:pluginSlug/edit" element={<ManageGate><PluginEditor /></ManageGate>} />
            <Route path="/manage/marketplaces/:slug/plugins/:pluginSlug/:componentType/new" element={<ManageGate><ComponentEditor /></ManageGate>} />
            <Route path="/manage/marketplaces/:slug/plugins/:pluginSlug/:componentType/:componentSlug/edit" element={<ManageGate><ComponentEditor /></ManageGate>} />

            {/* Legacy admin redirects */}
            <Route path="/admin" element={<Navigate to="/manage" replace />} />
            <Route path="/admin/new" element={<Navigate to="/manage/marketplaces/new" replace />} />
            <Route path="/admin/marketplaces/:slug" element={<Navigate to={window.location.pathname.replace("/admin", "/manage")} replace />} />
            <Route path="/admin/marketplaces/:slug/*" element={<Navigate to={window.location.pathname.replace("/admin", "/manage")} replace />} />
          </Route>
        </Routes>
      </AuthProvider>
    </BrowserRouter>
  );
}
