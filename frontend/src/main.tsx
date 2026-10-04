import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { createBrowserRouter, RouterProvider } from "react-router";
import Layout from "./components/Layout";
import "./index.css";
import Dashboard from "./pages/Dashboard";
import Managers from "./pages/Managers";
import ManagerPage from "./pages/ManagerPage";
import MatchPage from "./pages/MatchPage";
import Matches from "./pages/Matches";
import Models from "./pages/Models";
import Moneyball from "./pages/Moneyball";
import PlayerPage from "./pages/PlayerPage";
import Players from "./pages/Players";
import TeamPage from "./pages/TeamPage";
import Teams from "./pages/Teams";

const queryClient = new QueryClient({
  defaultOptions: { queries: { staleTime: 60_000, refetchOnWindowFocus: false, retry: 1 } },
});

const router = createBrowserRouter([
  {
    element: <Layout />,
    children: [
      { path: "/", element: <Dashboard /> },
      { path: "/moneyball", element: <Moneyball /> },
      { path: "/players", element: <Players /> },
      { path: "/players/:id", element: <PlayerPage /> },
      { path: "/matches", element: <Matches /> },
      { path: "/matches/:id", element: <MatchPage /> },
      { path: "/teams", element: <Teams /> },
      { path: "/teams/:id", element: <TeamPage /> },
      { path: "/managers", element: <Managers /> },
      { path: "/managers/:id", element: <ManagerPage /> },
      { path: "/models", element: <Models /> },
      { path: "*", element: <div className="py-20 text-center text-ink-3">Page not found.</div> },
    ],
  },
]);

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <QueryClientProvider client={queryClient}>
      <RouterProvider router={router} />
    </QueryClientProvider>
  </StrictMode>,
);
