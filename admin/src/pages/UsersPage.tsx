import { useState } from 'react';
import { useAdminUsers, useAdminUser } from '../api/hooks.ts';
import type { AdminUser } from '../api/types.ts';

export function UsersPage() {
  const [search, setSearch] = useState('');
  const [page, setPage] = useState(1);
  const [selectedUser, setSelectedUser] = useState<number | null>(null);

  const { data, isLoading, error } = useAdminUsers(search, page);

  return (
    <div>
      <h2 className="text-xl font-bold text-white mb-6">Users</h2>

      {/* Search */}
      <input
        type="text"
        placeholder="Search by tg_id, username, name..."
        value={search}
        onChange={(e) => { setSearch(e.target.value); setPage(1); }}
        className="w-full max-w-md text-sm px-4 py-3 rounded-xl bg-gray-900 border border-gray-800 text-white placeholder-gray-500 outline-none focus:border-indigo-500 transition-colors mb-4"
      />

      {isLoading && <Spinner />}
      {error && <ErrorMessage text="Failed to load users" />}

      {data && (
        <>
          <p className="text-xs text-gray-500 mb-3">{data.total} users found</p>

          {/* Users table */}
          <div className="bg-gray-900 rounded-xl border border-gray-800 overflow-hidden">
            <table className="w-full">
              <thead>
                <tr className="border-b border-gray-800">
                  <th className="text-left text-xs font-medium text-gray-500 px-4 py-3">User</th>
                  <th className="text-left text-xs font-medium text-gray-500 px-4 py-3">TG ID</th>
                  <th className="text-left text-xs font-medium text-gray-500 px-4 py-3">Server</th>
                  <th className="text-left text-xs font-medium text-gray-500 px-4 py-3">Registered</th>
                  <th className="text-left text-xs font-medium text-gray-500 px-4 py-3">Trial</th>
                </tr>
              </thead>
              <tbody>
                {data.users.map((u) => (
                  <UserRow
                    key={u.tg_id}
                    user={u}
                    selected={selectedUser === u.tg_id}
                    onClick={() => setSelectedUser(selectedUser === u.tg_id ? null : u.tg_id)}
                  />
                ))}
              </tbody>
            </table>
          </div>

          {/* Pagination */}
          {data.total > data.limit && (
            <div className="flex items-center justify-center gap-3 mt-4">
              <button
                onClick={() => setPage(page - 1)}
                disabled={page <= 1}
                className="text-sm px-4 py-2 rounded-lg font-medium bg-gray-800 text-gray-300 hover:bg-gray-700 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
              >
                Previous
              </button>
              <span className="text-sm text-gray-500">
                {page} / {Math.ceil(data.total / data.limit)}
              </span>
              <button
                onClick={() => setPage(page + 1)}
                disabled={page >= Math.ceil(data.total / data.limit)}
                className="text-sm px-4 py-2 rounded-lg font-medium bg-gray-800 text-gray-300 hover:bg-gray-700 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
              >
                Next
              </button>
            </div>
          )}
        </>
      )}

      {/* User detail panel */}
      {selectedUser !== null && (
        <UserDetailPanel tgId={selectedUser} onClose={() => setSelectedUser(null)} />
      )}
    </div>
  );
}

function UserRow({
  user,
  selected,
  onClick,
}: {
  user: AdminUser;
  selected: boolean;
  onClick: () => void;
}) {
  return (
    <tr
      onClick={onClick}
      className={`border-b border-gray-800/50 cursor-pointer transition-colors ${
        selected ? 'bg-indigo-600/10' : 'hover:bg-gray-800/50'
      }`}
    >
      <td className="px-4 py-3">
        <div className="text-sm font-medium text-white">{user.first_name}</div>
        {user.username && (
          <div className="text-xs text-gray-500">@{user.username}</div>
        )}
      </td>
      <td className="px-4 py-3 text-sm text-gray-400 font-mono">{user.tg_id}</td>
      <td className="px-4 py-3 text-sm text-gray-400">{user.server_name || '—'}</td>
      <td className="px-4 py-3 text-sm text-gray-400">{user.created_at?.split('T')[0] || '—'}</td>
      <td className="px-4 py-3">
        {user.is_trial_used ? (
          <span className="text-xs px-2 py-0.5 rounded-full bg-yellow-400/10 text-yellow-400">Used</span>
        ) : (
          <span className="text-xs px-2 py-0.5 rounded-full bg-gray-800 text-gray-500">Available</span>
        )}
      </td>
    </tr>
  );
}

function UserDetailPanel({ tgId, onClose }: { tgId: number; onClose: () => void }) {
  const { data, isLoading, error } = useAdminUser(tgId);

  return (
    <div className="fixed inset-0 bg-black/50 flex items-start justify-end z-50" onClick={onClose}>
      <div
        className="w-full max-w-md h-full bg-gray-900 border-l border-gray-800 p-6 overflow-y-auto"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between mb-6">
          <h3 className="text-lg font-bold text-white">User Detail</h3>
          <button
            onClick={onClose}
            className="text-gray-500 hover:text-gray-300 transition-colors"
          >
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <line x1="18" y1="6" x2="6" y2="18" />
              <line x1="6" y1="6" x2="18" y2="18" />
            </svg>
          </button>
        </div>

        {isLoading && <Spinner />}
        {error && <ErrorMessage text="Failed to load user details" />}

        {data && (
          <div className="space-y-5">
            {/* Basic info */}
            <div>
              <h4 className="text-sm font-semibold text-gray-300 mb-2">Profile</h4>
              <dl className="space-y-2">
                <InfoRow label="Name" value={data.first_name} />
                <InfoRow label="Username" value={data.username ? `@${data.username}` : '—'} />
                <InfoRow label="TG ID" value={String(data.tg_id)} mono />
                <InfoRow label="Registered" value={data.created_at?.split('T')[0] || '—'} />
                <InfoRow label="Server" value={data.server_name || '—'} />
                <InfoRow label="Trial" value={data.is_trial_used ? 'Used' : 'Available'} />
              </dl>
            </div>

            {/* VPN info */}
            <div>
              <h4 className="text-sm font-semibold text-gray-300 mb-2">VPN</h4>
              {data.vpn ? (
                <dl className="space-y-2">
                  <InfoRow
                    label="Status"
                    value={data.vpn.active ? 'Active' : 'Expired'}
                    valueColor={data.vpn.active ? 'text-green-400' : 'text-red-400'}
                  />
                  <InfoRow label="Devices" value={String(data.vpn.max_devices)} />
                  <InfoRow
                    label="Traffic"
                    value={`${formatBytes(data.vpn.traffic_used)} / ${formatBytes(data.vpn.traffic_total)}`}
                  />
                  {data.vpn.expiry_time > 0 && (
                    <InfoRow label="Expires" value={new Date(data.vpn.expiry_time).toLocaleDateString()} />
                  )}
                </dl>
              ) : (
                <p className="text-sm text-gray-500">No VPN subscription</p>
              )}
            </div>

            {/* Transactions */}
            {data.transactions.length > 0 && (
              <div>
                <h4 className="text-sm font-semibold text-gray-300 mb-2">
                  Transactions ({data.transactions.length})
                </h4>
                <div className="space-y-1.5">
                  {data.transactions.map((tx) => (
                    <div
                      key={tx.id}
                      className="flex justify-between text-sm px-3 py-2 rounded-lg bg-gray-800/50"
                    >
                      <span className="text-gray-400">{tx.created_at?.split('T')[0] || '—'}</span>
                      <span className={tx.status === 'completed' ? 'text-green-400' : 'text-gray-500'}>
                        {tx.status || '—'}
                      </span>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

function InfoRow({
  label,
  value,
  mono,
  valueColor,
}: {
  label: string;
  value: string;
  mono?: boolean;
  valueColor?: string;
}) {
  return (
    <div className="flex justify-between text-sm">
      <span className="text-gray-500">{label}</span>
      <span className={`${valueColor || 'text-gray-200'} ${mono ? 'font-mono' : ''}`}>{value}</span>
    </div>
  );
}

function formatBytes(bytes: number): string {
  if (bytes === 0) return '0 B';
  const k = 1024;
  const sizes = ['B', 'KB', 'MB', 'GB', 'TB'];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + ' ' + sizes[i];
}

function Spinner() {
  return (
    <div className="flex items-center justify-center h-32">
      <div className="animate-spin rounded-full h-6 w-6 border-2 border-indigo-500 border-t-transparent" />
    </div>
  );
}

function ErrorMessage({ text }: { text: string }) {
  return (
    <div className="flex flex-col items-center justify-center h-32 gap-2">
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
