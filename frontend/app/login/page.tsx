"use client";

import { Suspense } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { login } from "@/lib/auth";
import { parseApiError } from "@/lib/apiError";
import { loginSchema, type LoginFormValues } from "@/lib/schemas/login";
import clsx from "clsx";

function LoginForm() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const redirectTo = searchParams.get("from") ?? "/monitor";

  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
    setError,
  } = useForm<LoginFormValues>({
    resolver: zodResolver(loginSchema),
    defaultValues: { username: "", password: "" },
  });

  async function onSubmit(values: LoginFormValues) {
    try {
      await login(values.username, values.password);
      const target =
        redirectTo.startsWith("/") && !redirectTo.startsWith("/login")
          ? redirectTo
          : "/monitor";
      router.replace(target);
    } catch (err: unknown) {
      setError("root", { message: parseApiError(err) });
    }
  }

  const rootError = errors.root?.message;

  return (
    <div className="min-h-screen flex items-center justify-center bg-surface-900 px-4">
      <div className="w-full max-w-sm bg-surface-800 rounded-2xl shadow-xl p-8 border border-surface-700">
        <div className="mb-8 text-center">
          <div className="inline-flex items-center justify-center w-14 h-14 rounded-full bg-accent/10 mb-3">
            <svg
              className="w-7 h-7 text-accent"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
              aria-hidden
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={1.8}
                d="M15 10l4.553-2.276A1 1 0 0121 8.723v6.554a1 1 0 01-1.447.894L15 14M3 8a2 2 0 012-2h8a2 2 0 012 2v8a2 2 0 01-2 2H5a2 2 0 01-2-2V8z"
              />
            </svg>
          </div>
          <h1 className="text-xl font-bold text-white tracking-wide">
            Smart Vision System
          </h1>
          <p className="text-sm text-surface-400 mt-1">
            Sign in to access the dashboard
          </p>
        </div>

        {rootError && (
          <div
            role="alert"
            className="mb-4 rounded-lg bg-severity-high/10 border border-severity-high/40 px-4 py-3 text-sm text-severity-high"
          >
            {rootError}
          </div>
        )}

        <form onSubmit={handleSubmit(onSubmit)} className="space-y-4" noValidate>
          <div>
            <label
              htmlFor="username"
              className="block text-xs font-medium text-surface-300 mb-1.5 uppercase tracking-wider"
            >
              Username
            </label>
            <input
              id="username"
              type="text"
              autoComplete="username"
              aria-invalid={!!errors.username}
              className={clsx(
                "w-full bg-surface-900 border rounded-lg px-4 py-2.5 text-sm text-white placeholder-surface-500 focus:outline-none focus:ring-2 focus:ring-accent focus:border-transparent transition",
                errors.username ? "border-severity-high" : "border-surface-600"
              )}
              placeholder="admin"
              {...register("username")}
            />
            {errors.username && (
              <p className="mt-1.5 text-xs text-severity-high">
                {errors.username.message}
              </p>
            )}
          </div>

          <div>
            <label
              htmlFor="password"
              className="block text-xs font-medium text-surface-300 mb-1.5 uppercase tracking-wider"
            >
              Password
            </label>
            <input
              id="password"
              type="password"
              autoComplete="current-password"
              aria-invalid={!!errors.password}
              className={clsx(
                "w-full bg-surface-900 border rounded-lg px-4 py-2.5 text-sm text-white placeholder-surface-500 focus:outline-none focus:ring-2 focus:ring-accent focus:border-transparent transition",
                errors.password ? "border-severity-high" : "border-surface-600"
              )}
              placeholder="••••••••"
              {...register("password")}
            />
            {errors.password && (
              <p className="mt-1.5 text-xs text-severity-high">
                {errors.password.message}
              </p>
            )}
          </div>

          <button
            type="submit"
            disabled={isSubmitting}
            className="w-full mt-2 bg-accent hover:bg-accent/80 disabled:opacity-50 disabled:cursor-not-allowed text-white font-semibold py-2.5 rounded-lg transition text-sm"
          >
            {isSubmitting ? "Signing in…" : "Sign In"}
          </button>
        </form>
{/* 
        <p className="mt-4 text-center text-xs text-surface-500">
          First-time default: <span className="font-mono text-surface-400">admin</span> /{" "}
          <span className="font-mono text-surface-400">changeme</span>
        </p> */}

        <p className="mt-4 text-center text-xs text-surface-500">
          Smart Vision System · Graduation Project
        </p>
      </div>
    </div>
  );
}

export default function LoginPage() {
  return (
    <Suspense
      fallback={
        <div className="min-h-screen flex items-center justify-center bg-surface-900 text-surface-400 text-sm">
          Loading…
        </div>
      }
    >
      <LoginForm />
    </Suspense>
  );
}
