import { defer, type LoaderFunctionArgs } from "react-router-dom";

export function createDeferredLoader<T>(key: string, load: (args: LoaderFunctionArgs) => Promise<T>) {
  return (args: LoaderFunctionArgs) => defer({ [key]: load(args) });
}
