import { Suspense, type ReactNode } from "react";
import { Await, useAsyncError } from "react-router-dom";

import { getErrorMessage } from "../api/errors";

type StatusCardProps = {
  label: string;
  title: string;
  message: string;
  error?: boolean;
};

function RouteStatusCard({ label, title, message, error = false }: StatusCardProps) {
  return (
    <section className={`status-card${error ? " status-card-error" : ""}`}>
      <p className="status-label">{label}</p>
      <h2>{title}</h2>
      <p>{message}</p>
    </section>
  );
}

function AsyncRouteError({
  label,
  title,
  fallbackMessage,
}: {
  label: string;
  title: string;
  fallbackMessage: string;
}) {
  const error = useAsyncError();

  return (
    <RouteStatusCard
      label={label}
      title={title}
      message={getErrorMessage(error, fallbackMessage)}
      error
    />
  );
}

type AsyncRouteContentProps<T> = {
  resolve: Promise<T>;
  loading: StatusCardProps;
  error: Omit<StatusCardProps, "error">;
  children: (data: T) => ReactNode;
};

export function AsyncRouteContent<T>({
  resolve,
  loading,
  error,
  children,
}: AsyncRouteContentProps<T>) {
  return (
    <Suspense fallback={<RouteStatusCard {...loading} />}>
      <Await
        resolve={resolve}
        errorElement={
          <AsyncRouteError
            label={error.label}
            title={error.title}
            fallbackMessage={error.message}
          />
        }
      >
        {children}
      </Await>
    </Suspense>
  );
}
