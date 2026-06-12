import type { Metadata } from "next";
import { DM_Sans } from "next/font/google";
import "flag-icons/css/flag-icons.min.css";
import "./globals.css";

const dmSans = DM_Sans({
  subsets: ["latin"],
  weight: ["400", "500", "600", "700"],
  variable: "--font-dm-sans",
});

export const metadata: Metadata = {
  title: "SyncUp",
  description: "Find your people through taste across games, music, film, anime, and communities.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" className={dmSans.variable}>
      <body className={`${dmSans.className} antialiased`}>{children}</body>
    </html>
  );
}
