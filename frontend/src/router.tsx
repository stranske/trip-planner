import { createBrowserRouter, type RouteObject } from "react-router-dom";

import App from "./App";
import { healthLoader, HealthPage } from "./routes/HealthPage";
import { workspaceLoader, WorkspacePage } from "./routes/WorkspacePage";

export const appRoutes: RouteObject[] = [
  {
    path: "/",
    element: <App />,
    children: [
      {
        index: true,
        element: <HealthPage />,
        loader: healthLoader,
      },
      {
        path: "workspace/:tripId",
        element: <WorkspacePage />,
        loader: workspaceLoader,
      },
    ],
  },
];

export const router = createBrowserRouter(appRoutes, {
  future: {
    v7_normalizeFormMethod: true,
    v7_partialHydration: true,
  },
});
