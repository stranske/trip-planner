import {
  createBrowserRouter,
  redirect,
  type LoaderFunctionArgs,
  type RouteObject,
} from "react-router-dom";

import { fetchCurrentSession } from "./api/auth";
import { fetchTrip, fetchTrips } from "./api/trips";
import { fetchWorkspace } from "./api/workspace";
import App from "./App";
import { ApiClientError } from "./lib/api/errors";
import { healthLoader, HealthPage } from "./routes/HealthPage";
import { LoginPage } from "./routes/LoginPage";
import { NewTripPage } from "./routes/NewTripPage";
import { SignupPage } from "./routes/SignupPage";
import { TripDetailPage } from "./routes/TripDetailPage";
import { TripsPage } from "./routes/TripsPage";
import { WorkspacePage } from "./routes/WorkspacePage";

const DEFAULT_WORKSPACE_TRIP = "trip-leisure-kyoto-draft";
const DEFAULT_SIGNED_IN_ROUTE = "/trips";
const sessionLoadCache = new Map<string, Promise<RootLoaderData>>();

export type RootLoaderData = {
  session: Awaited<ReturnType<typeof fetchCurrentSession>> | null;
};

function isUnauthorized(error: unknown): error is ApiClientError {
  return error instanceof ApiClientError && error.status === 401;
}

function loadSession(request: Request): Promise<RootLoaderData> {
  const cached = sessionLoadCache.get(request.url);
  if (cached) {
    return cached;
  }

  const pending = (async () => {
    try {
      return { session: await fetchCurrentSession() };
    } catch (error) {
      if (isUnauthorized(error)) {
        return { session: null };
      }
      throw error;
    }
  })();

  sessionLoadCache.set(request.url, pending);
  pending.finally(() => {
    queueMicrotask(() => {
      if (sessionLoadCache.get(request.url) === pending) {
        sessionLoadCache.delete(request.url);
      }
    });
  });
  return pending;
}

export async function rootLoader({ request }: LoaderFunctionArgs): Promise<RootLoaderData> {
  return loadSession(request);
}

export async function indexLoader({ request }: LoaderFunctionArgs) {
  const { session } = await loadSession(request);
  if (session) {
    throw redirect(DEFAULT_SIGNED_IN_ROUTE);
  }
  throw redirect("/login");
}

export async function authPageLoader({ request }: LoaderFunctionArgs) {
  const { session } = await loadSession(request);
  if (session) {
    throw redirect(DEFAULT_SIGNED_IN_ROUTE);
  }
  return null;
}

function redirectToLogin(request: Request): never {
  const nextPath = new URL(request.url).pathname;
  throw redirect(`/login?next=${encodeURIComponent(nextPath)}`);
}

export async function protectedTripsLoader({ request }: LoaderFunctionArgs) {
  const { session } = await loadSession(request);
  if (!session) {
    redirectToLogin(request);
  }

  return {
    trips: fetchTrips(),
  };
}

export async function protectedTripDetailLoader({
  params,
  request,
}: LoaderFunctionArgs) {
  const { session } = await loadSession(request);
  if (!session) {
    redirectToLogin(request);
  }

  return {
    trip: fetchTrip(params.tripId ?? ""),
  };
}

export async function protectedCreateTripLoader({ request }: LoaderFunctionArgs) {
  const { session } = await loadSession(request);
  if (!session) {
    redirectToLogin(request);
  }
  return null;
}

export async function protectedWorkspaceLoader({ params, request }: LoaderFunctionArgs) {
  const { session } = await loadSession(request);
  if (!session) {
    redirectToLogin(request);
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
        path: "trips",
        element: <TripsPage />,
        loader: protectedTripsLoader,
      },
      {
        path: "trips/new",
        element: <NewTripPage />,
        loader: protectedCreateTripLoader,
      },
      {
        path: "trips/:tripId",
        element: <TripDetailPage />,
        loader: protectedTripDetailLoader,
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
