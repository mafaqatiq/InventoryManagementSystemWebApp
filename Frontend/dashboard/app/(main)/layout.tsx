import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google"; 
import { ThemeProvider } from "@/components/theme-provider";
import Head from "next/head";


const geistSans = Geist({
    variable: "--font-geist-sans",
    subsets: ["latin"],
  });
  
  const geistMono = Geist_Mono({
    variable: "--font-geist-mono",
    subsets: ["latin"],
  });
  
  export const metadata: Metadata = {
    title: "Dashboard",
    description: "Developed by Afaq",
  };

  
export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    
        <ThemeProvider
          attribute="class"
          defaultTheme="system"
          enableSystem
          disableTransitionOnChange
        >
            <header className="border-2 p-8 mt-1  rounded-2xl">This is navbar</header>
          {children}
        </ThemeProvider>
  );
}
