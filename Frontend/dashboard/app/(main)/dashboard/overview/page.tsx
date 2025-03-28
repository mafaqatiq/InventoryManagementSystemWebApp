'use client';

import { motion } from 'framer-motion';

// pages/dashboard.tsx (Static Mock)
export default function Dashboard() {
  // Mock data
  const stats = {
    totalProducts: 42,
    totalOrders: 128,
    lowStock: 5,
  };

  const recentOrders = [
    { id: "ORD-001", product: "T-Shirt", status: "Delivered" },
    { id: "ORD-002", product: "Sneakers", status: "Processing" },
  ];

  return (
    <div className="p-6">
      {/* Stats Cards */}
      <div className="grid grid-cols-3 gap-4 mb-8 text-white">
        <div className="bg-black border p-4 rounded-lg shadow">
          <h3 className="text-gray-500">Total Products</h3>
          <p className="text-2xl font-bold">{stats.totalProducts}</p>
        </div>
        <div className="bg-black border p-4 rounded-lg shadow">
          <h3 className="text-gray-500">Total Orders</h3>
          <p className="text-2xl font-bold">{stats.totalOrders}</p>
        </div>
        <div className="bg-black border p-4 rounded-lg shadow">
          <h3 className="text-gray-500">Low Stock</h3>
          <p className="text-2xl font-bold">{stats.lowStock}</p>
        </div>
      </div>

      {/* Recent Orders Table */}
      <div className="bg-black border p-4 rounded-lg shadow ">
        <h2 className="text-xl font-semibold mb-4">Recent Orders</h2>
        <table className="w-full">
          <thead>
            <tr className="border-b">
              <th className="text-left p-2">Order ID</th>
              <th className="text-left p-2">Product</th>
              <th className="text-left p-2">Status</th>
            </tr>
          </thead>
          <tbody>
            {recentOrders.map((order) => (
              <tr key={order.id} className="border-b hover:bg-gray-900">
                <td className="p-2">{order.id}</td>
                <td className="p-2">{order.product}</td>
                <td className="p-2">
                  <span className={`px-2 py-1 rounded-full text-xs ${
                    order.status === "Delivered" 
                      ? "bg-green-100 text-green-800" 
                      : "bg-yellow-100 text-yellow-800"
                  }`}>
                    {order.status}
                  </span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}