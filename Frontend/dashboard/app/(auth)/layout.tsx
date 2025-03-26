export default function AuthLayout({
    children,
  }: {
    children: React.ReactNode
  }) {
    return (
      <div className="container p-8">
        <div className="w-full border-4 rounded-xl shadow">
          <div >
            <h1 className="text-3xl font-bold">MyStore</h1>
            <p className="mt-2 text-gray-600">Admin Dashboard</p>
          </div>
        </div>
          {children}
      </div>
    )
  }