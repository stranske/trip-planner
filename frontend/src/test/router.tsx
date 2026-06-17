import type { PropsWithChildren, ReactElement } from "react";
import { MemoryRouter } from "react-router-dom";

export function TestMemoryRouter({ children }: PropsWithChildren): ReactElement {
  return <MemoryRouter>{children}</MemoryRouter>;
}
