import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import { headers } from "next/headers";
import "./globals.css";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

export async function generateMetadata(): Promise<Metadata> {
  const requestHeaders = await headers();
  const host = requestHeaders.get("x-forwarded-host") ??
    requestHeaders.get("host") ??
    "localhost:3000";
  const protocol = requestHeaders.get("x-forwarded-proto") ??
    (host.startsWith("localhost") || host.startsWith("127.0.0.1")
      ? "http"
      : "https");
  const origin = new URL(`${protocol}://${host}`);
  const description =
    "A precise browser workspace for live camera object detection, tracking, and performance monitoring.";

  return {
    metadataBase: origin,
    title: "VisionDesk — Real-time Object Detection",
    description,
    openGraph: {
      title: "VisionDesk",
      description: "Real-time object intelligence",
      type: "website",
      url: origin,
      images: [
        {
          url: new URL("/og.png", origin).toString(),
          width: 1704,
          height: 896,
          alt: "VisionDesk real-time object intelligence",
        },
      ],
    },
    twitter: {
      card: "summary_large_image",
      title: "VisionDesk",
      description: "Real-time object intelligence",
      images: [new URL("/og.png", origin).toString()],
    },
  };
}

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body className={`${geistSans.variable} ${geistMono.variable}`}>
        {children}
      </body>
    </html>
  );
}
