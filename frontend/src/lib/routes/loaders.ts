import type { LoaderFunctionArgs } from "react-router-dom";

export function createDeferredLoader<T>(key: string, load: (args: LoaderFunctionArgs) => Promise<T>) {
  return (args: LoaderFunctionArgs) => ({ [key]: load(args) });
}
