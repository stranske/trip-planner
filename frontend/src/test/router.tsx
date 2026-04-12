import type { PropsWithChildren } from "react";
import { MemoryRouter } from "react-router-dom";

export const TEST_ROUTER_FUTURE = {
  v7_normalizeFormMethod: true,
  v7_partialHydration: true,
  v7_relativeSplatPath: true,
  v7_startTransition: true,
} as const;

export function TestMemoryRouter({ children }: PropsWithChildren): JSX.Element {
  return <MemoryRouter future={TEST_ROUTER_FUTURE}>{children}</MemoryRouter>;
}
