import { BrowserRouter, Route, Routes } from "react-router-dom";
import MarketplacesList from "./pages/MarketplacesList";
import NewMarketplace from "./pages/NewMarketplace";
import MarketplaceDetail from "./pages/MarketplaceDetail";
import SkillEditor from "./pages/SkillEditor";

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<MarketplacesList />} />
        <Route path="/new" element={<NewMarketplace />} />
        <Route path="/m/:slug" element={<MarketplaceDetail />} />
        <Route path="/m/:slug/skills/new" element={<SkillEditor />} />
        <Route path="/m/:slug/skills/:skillSlug/edit" element={<SkillEditor />} />
      </Routes>
    </BrowserRouter>
  );
}
