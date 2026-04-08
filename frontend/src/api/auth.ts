import { fetchJson } from "../lib/api/client";

export type SessionUser = {
  user_id: string;
  email: string;
  display_name: string;
};

export type SessionPayload = {
  user: SessionUser;
};

export type LoginPayload = {
  email: string;
  password: string;
};

export type SignupPayload = LoginPayload & {
  display_name: string;
};

export async function fetchCurrentSession(): Promise<SessionPayload> {
  return fetchJson<SessionPayload>({
    path: "/api/auth/session",
    credentials: "include",
  });
}

export async function login(payload: LoginPayload): Promise<SessionPayload> {
  return fetchJson<SessionPayload>({
    path: "/api/auth/login",
    method: "POST",
    credentials: "include",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
}

export async function signup(payload: SignupPayload): Promise<SessionPayload> {
  return fetchJson<SessionPayload>({
    path: "/api/auth/signup",
    method: "POST",
    credentials: "include",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
}

export async function logout(): Promise<{ signed_out: boolean }> {
  return fetchJson<{ signed_out: boolean }>({
    path: "/api/auth/logout",
    method: "POST",
    credentials: "include",
  });
}
