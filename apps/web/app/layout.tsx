import type { Metadata } from "next";
import "./globals.css";
import { Toaster } from "sonner";

import { AuthProvider } from "@/components/providers/AuthProvider";

export const metadata: Metadata = {
  title: "LeilMat — AI-Native Alloy Design",
  description: "Design metallic alloys with AI-powered property prediction, inverse design, and phase diagram analysis.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className="dark">
      <body>
        <AuthProvider>
          {children}
          <Toaster theme="dark" position="bottom-right" />
        </AuthProvider>
      </body>
    </html>
  );
}
