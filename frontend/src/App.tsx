import { BrowserRouter, Route, Routes } from "react-router-dom";
import BrowseMarketplaces from "./pages/BrowseMarketplaces";
import BrowseMarketplaceDetail from "./pages/BrowseMarketplaceDetail";
import MarketplacesList from "./pages/MarketplacesList";
import NewMarketplace from "./pages/NewMarketplace";
import MarketplaceDetail from "./pages/MarketplaceDetail";
import PluginEditor from "./pages/PluginEditor";
import ComponentEditor from "./pages/ComponentEditor";

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        {/* Consumer browsing */}
        <Route path="/" element={<BrowseMarketplaces />} />
        <Route path="/marketplaces/:slug" element={<BrowseMarketplaceDetail />} />

        {/* Admin */}
        <Route path="/admin" element={<MarketplacesList />} />
        <Route path="/admin/new" element={<NewMarketplace />} />
        <Route path="/admin/marketplaces/:slug" element={<MarketplaceDetail />} />
        <Route path="/admin/marketplaces/:slug/plugins/new" element={<PluginEditor />} />
        <Route path="/admin/marketplaces/:slug/plugins/:pluginSlug/edit" element={<PluginEditor />} />
        <Route path="/admin/marketplaces/:slug/plugins/:pluginSlug/:componentType/:componentSlug/edit" element={<ComponentEditor />} />
      </Routes>
    </BrowserRouter>
  );
}
