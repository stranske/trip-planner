import React from "react";
import ReactDOM from "react-dom/client";
import { RouterProvider } from "react-router-dom";

import { router } from "./router";
// Shared design system (kit) imported before the app stylesheet so local tokens
// and components draw from the fleet theme-air palette.
import "./design-system/ds-tokens.css";
import "./design-system/ds-components.css";
import "./design-system/reconcile.css";
import "./styles.css";

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <RouterProvider router={router} />
  </React.StrictMode>
);
