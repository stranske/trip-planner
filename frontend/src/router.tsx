import {
  createBrowserRouter,
  redirect,
  type LoaderFunctionArgs,
  type RouteObject,
} from "react-router-dom";

import { fetchCurrentSession } from "./api/auth";
import { fetchWorkspace } from "./api/workspace";
import App from "./App";
import { ApiClientError } from "./lib/api/errors";
import { healthLoader, HealthPage } from "./routes/HealthPage";
import { LoginPage } from "./routes/LoginPage";
import { SignupPage } from "./routes/SignupPage";
import { WorkspacePage } from "./routes/WorkspacePage";

const DEFAULT_WORKSPACE_TRIP = "trip-leisure-kyoto-draft";

export type RootLoaderData = {
  session: Awaited<ReturnType<typeof fetchCurrentSession>> | null;
};

function isUnauthorized(error: unknown): error is ApiClientError {
  return error instanceof ApiClientError && error.status === 401;
}

export async function rootLoader(): Promise<RootLoaderData> {
  try {
    return { session: await fetchCurrentSession() };
  } catch (error) {
    if (isUnauthorized(error)) {
      return { session: null };
    }
    throw error;
  }
}

export async function indexLoader() {
  const { session } = await rootLoader();
  if (session) {
    throw redirect(`/workspace/${DEFAULT_WORKSPACE_TRIP}`);
  }
  throw redirect("/login");
}

export async function authPageLoader() {
  const { session } = await rootLoader();
  if (session) {
    throw redirect(`/workspace/${DEFAULT_WORKSPACE_TRIP}`);
  }
  return null;
}

export async function protectedWorkspaceLoader({ params, request }: LoaderFunctionArgs) {
  try {
    await fetchCurrentSession();
  } catch (error) {
    if (isUnauthorized(error)) {
      const nextPath = new URL(request.url).pathname;
      throw redirect(`/login?next=${encodeURIComponent(nextPath)}`);
    }
    throw error;
  }

  return {
    workspace: fetchWorkspace(params.tripId ?? DEFAULT_WORKSPACE_TRIP),
  };
}

export const appRoutes: RouteObject[] = [
  {
    path: "/",
    id: "root",
    element: <App />,
    loader: rootLoader,
    children: [
      {
        index: true,
        loader: indexLoader,
      },
      {
        path: "health",
        element: <HealthPage />,
        loader: healthLoader,
      },
      {
        path: "login",
        element: <LoginPage />,
        loader: authPageLoader,
      },
      {
        path: "signup",
        element: <SignupPage />,
        loader: authPageLoader,
      },
      {
        path: "workspace/:tripId",
        element: <WorkspacePage />,
        loader: protectedWorkspaceLoader,
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
