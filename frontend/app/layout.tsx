"use client";

import "./globals.css";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { useState } from "react";

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 30_000,
      retry: 2,
    },
  },
});

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const [client] = useState(() => queryClient);

  return (
    <html lang="en">
      <head>
        <title>Smart Vision System</title>
        <meta name="description" content="AI-powered surveillance dashboard" />
        <link rel="icon" href="/favicon.ico" />
      </head>
      <body className="min-h-screen bg-surface-900 text-white antialiased">
        <QueryClientProvider client={client}>{children}</QueryClientProvider>
      </body>
    </html>
  );
}
