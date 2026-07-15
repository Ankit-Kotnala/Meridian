"use client";

import type { components } from "@careeros/contracts";

import {
  ApiRequestError,
  apiMutation,
  requestErrorMessage,
} from "@/shared/api/browser-request";

export { ApiRequestError as AuthRequestError };

export async function registerAccount(
  input: components["schemas"]["RegisterRequest"],
): Promise<void> {
  await apiMutation("/api/v1/auth/register", {
    method: "POST",
    body: JSON.stringify(input),
  });
}

export async function resendVerification(email: string): Promise<void> {
  await apiMutation("/api/v1/auth/resend-verification", {
    method: "POST",
    body: JSON.stringify({ email }),
  });
}

export async function verifyEmail(token: string): Promise<void> {
  await apiMutation("/api/v1/auth/verify-email", {
    method: "POST",
    body: JSON.stringify({ token }),
  });
}

export async function login(
  input: components["schemas"]["LoginRequest"],
): Promise<void> {
  await apiMutation("/api/v1/auth/login", {
    method: "POST",
    body: JSON.stringify(input),
  });
}

export async function forgotPassword(email: string): Promise<void> {
  await apiMutation("/api/v1/auth/forgot-password", {
    method: "POST",
    body: JSON.stringify({ email }),
  });
}

export async function resetPassword(
  token: components["schemas"]["ResetPasswordRequest"]["token"],
  newPassword: components["schemas"]["ResetPasswordRequest"]["newPassword"],
): Promise<void> {
  await apiMutation("/api/v1/auth/reset-password", {
    method: "POST",
    body: JSON.stringify({ newPassword, token }),
  });
}

export async function logout(): Promise<void> {
  await apiMutation(
    "/api/v1/auth/logout",
    { method: "POST" },
    { csrf: "session" },
  );
}

export async function logoutAll(): Promise<void> {
  await apiMutation(
    "/api/v1/auth/logout-all",
    { method: "POST" },
    { csrf: "session" },
  );
}

export function googleAuthorizationUrl(returnTo: string): string {
  return `/api/v1/auth/google/start?returnTo=${encodeURIComponent(returnTo)}`;
}

export function authErrorMessage(error: unknown, fallback: string): string {
  return requestErrorMessage(error, fallback);
}
