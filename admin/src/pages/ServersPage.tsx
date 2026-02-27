import { useAdminServers } from '../api/hooks.ts';

export function ServersPage() {
  const { data, isLoading, error } = useAdminServers();

  if (isLoading) return <Spinner />;
  if (error || !data) return <ErrorMessage text="Failed to load servers" />;

  return (
    <div>
      <h2 className="text-xl font-bold text-white mb-6">Servers</h2>

      <div className="bg-gray-900 rounded-xl border border-gray-800 overflow-hidden">
        <table className="w-full">
          <thead>
            <tr className="border-b border-gray-800">
              <th className="text-left text-xs font-medium text-gray-500 px-4 py-3">Status</th>
              <th className="text-left text-xs font-medium text-gray-500 px-4 py-3">Name</th>
              <th className="text-left text-xs font-medium text-gray-500 px-4 py-3">Host</th>
              <th className="text-left text-xs font-medium text-gray-500 px-4 py-3">Location</th>
              <th className="text-left text-xs font-medium text-gray-500 px-4 py-3">Clients</th>
            </tr>
          </thead>
          <tbody>
            {data.servers.map((s) => (
              <tr key={s.id} className="border-b border-gray-800/50 hover:bg-gray-800/30 transition-colors">
                <td className="px-4 py-3">
                  <div className="flex items-center gap-2">
                    <div
                      className="w-2.5 h-2.5 rounded-full"
                      style={{ backgroundColor: s.online ? '#34d399' : '#f87171' }}
                    />
                    <span className={`text-xs font-medium ${s.online ? 'text-green-400' : 'text-red-400'}`}>
                      {s.online ? 'Online' : 'Offline'}
                    </span>
                  </div>
                </td>
                <td className="px-4 py-3 text-sm font-medium text-white">{s.name}</td>
                <td className="px-4 py-3 text-sm text-gray-400 font-mono">{s.host}</td>
                <td className="px-4 py-3 text-sm text-gray-400">{s.location || '—'}</td>
                <td className="px-4 py-3">
                  <div className="flex items-center gap-2">
                    <span className="text-sm text-gray-300">{s.current_clients}</span>
                    <span className="text-xs text-gray-600">/ {s.max_clients}</span>
                    {/* Usage bar */}
                    <div className="w-16 h-1.5 rounded-full bg-gray-800 overflow-hidden">
                      <div
                        className="h-full rounded-full transition-all"
                        style={{
                          width: `${Math.min(100, (s.current_clients / s.max_clients) * 100)}%`,
                          backgroundColor: s.current_clients / s.max_clients > 0.8 ? '#f87171' : '#818cf8',
                        }}
                      />
                    </div>
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
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
