export default function MainLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    // Remove ThemeProvider since it's already in root layout
    <div className="container mx-auto px-4">
      <header className="border-2 p-8 mt-1 rounded-2xl mb-6">
        This is navbar
      </header>
      <main>{children}</main>
    </div>
  )
}