import type { Metadata, Viewport } from "next";
import "./globals.css";
import { Toaster } from "sonner";

import { AuthProvider } from "@/components/providers/AuthProvider";
import { ComputeJobsProvider } from "@/components/providers/ComputeJobsProvider";
import { LeilHeader } from "@/components/LeilHeader";

export const metadata: Metadata = {
  title: "LeilMat — AI-Native Alloy Design",
  description: "Design metallic alloys with AI-powered property prediction, inverse design, and phase diagram analysis.",
};

// Without an explicit viewport, mobile browsers assume a ~980px layout and
// zoom the desktop-first canvas out to an unreadable size.  Pin to the
// device width (still allowing pinch-zoom up to 5× for accessibility).
export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
  maximumScale: 5,
  themeColor: "#141414",   // Ink: the browser chrome matches the cockpit
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className="dark">
      <body>
        <AuthProvider>
          <ComputeJobsProvider />
          <LeilHeader />
          {children}
          <Toaster theme="dark" position="bottom-right" />
        </AuthProvider>
      </body>
    </html>
  );
}
