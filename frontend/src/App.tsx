import { BrowserRouter, Route, Routes } from "react-router-dom";
import MarketplacesList from "./pages/MarketplacesList";
import NewMarketplace from "./pages/NewMarketplace";
import MarketplaceDetail from "./pages/MarketplaceDetail";
import PluginEditor from "./pages/PluginEditor";

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<MarketplacesList />} />
        <Route path="/new" element={<NewMarketplace />} />
        <Route path="/marketplace/:slug" element={<MarketplaceDetail />} />
        <Route path="/marketplace/:slug/plugins/new" element={<PluginEditor />} />
        <Route path="/marketplace/:slug/plugins/:pluginSlug/edit" element={<PluginEditor />} />
      </Routes>
    </BrowserRouter>
  );
}
