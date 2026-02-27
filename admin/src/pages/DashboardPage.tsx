import { useAdminStats } from '../api/hooks.ts';

export function DashboardPage() {
  const { data, isLoading, error } = useAdminStats();

  if (isLoading) return <Spinner />;
  if (error || !data) return <ErrorMessage text="Failed to load stats" />;

  return (
    <div>
      <h2 className="text-xl font-bold text-white mb-6">Dashboard</h2>

      {/* Stat cards */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
        <StatCard label="Total Users" value={data.total_users} />
        <StatCard label="Active Subs" value={data.active_subscriptions || '—'} />
        {Object.entries(data.revenue).map(([currency, amount]) => (
          <StatCard key={currency} label={`Revenue (${currency})`} value={amount} />
        ))}
      </div>

      {/* Charts section */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Registrations 30d */}
        {data.registrations_30d.length > 0 && (
          <div className="bg-gray-900 rounded-xl border border-gray-800 p-5">
            <h3 className="text-sm font-semibold text-gray-300 mb-4">
              Registrations (30d)
            </h3>
            <div className="space-y-1.5 max-h-80 overflow-y-auto">
              {data.registrations_30d.map((r) => (
                <div
                  key={r.date}
                  className="flex justify-between text-sm px-3 py-2 rounded-lg bg-gray-800/50"
                >
                  <span className="text-gray-400">{r.date}</span>
                  <span className="font-medium text-green-400">+{r.count}</span>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Payments 30d */}
        {data.payments_30d.length > 0 && (
          <div className="bg-gray-900 rounded-xl border border-gray-800 p-5">
            <h3 className="text-sm font-semibold text-gray-300 mb-4">
              Payments (30d)
            </h3>
            <div className="space-y-1.5 max-h-80 overflow-y-auto">
              {data.payments_30d.map((p) => (
                <div
                  key={p.date}
                  className="flex justify-between text-sm px-3 py-2 rounded-lg bg-gray-800/50"
                >
                  <span className="text-gray-400">{p.date}</span>
                  <span className="font-medium text-indigo-400">{p.count} txns</span>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

function StatCard({ label, value }: { label: string; value: string | number }) {
  return (
    <div className="bg-gray-900 rounded-xl border border-gray-800 p-4">
      <div className="text-xs text-gray-500 mb-1">{label}</div>
      <div className="text-2xl font-bold text-white">{value}</div>
    </div>
  );
}

function Spinner() {
  return (
    <div className="flex items-center justify-center h-64">
      <div className="animate-spin rounded-full h-8 w-8 border-2 border-indigo-500 border-t-transparent" />
    </div>
  );
}

function ErrorMessage({ text }: { text: string }) {
  return (
    <div className="flex flex-col items-center justify-center h-64 gap-3">
      <p className="text-sm text-gray-400">{text}</p>
      <button
        onClick={() => window.location.reload()}
        className="text-sm font-medium px-4 py-2 rounded-lg bg-indigo-600 text-white hover:bg-indigo-700 transition-colors"
      >
        Retry
      </button>
    </div>
  );
}
