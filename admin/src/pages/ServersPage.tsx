import { useState } from 'react';
import type { FormEvent, HTMLAttributes } from 'react';
import { ApiRequestError } from '../api/client.ts';
import { useAdminServers, useUpdateAdminServer } from '../api/hooks.ts';
import type { AdminServer, AdminServerUpdatePayload } from '../api/types.ts';

export function ServersPage() {
  const { data, isLoading, error } = useAdminServers();
  const updateServer = useUpdateAdminServer();
  const [editingServer, setEditingServer] = useState<AdminServer | null>(null);
  const [formState, setFormState] = useState<ServerFormState | null>(null);
  const [formError, setFormError] = useState<string | null>(null);

  if (isLoading) return <Spinner />;
  if (error || !data) return <ErrorMessage text="Failed to load servers" />;

  function openEditor(server: AdminServer) {
    setEditingServer(server);
    setFormState(createFormState(server));
    setFormError(null);
  }

  function closeEditor() {
    setEditingServer(null);
    setFormState(null);
    setFormError(null);
    updateServer.reset();
  }

  async function handleSave(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!editingServer || !formState) return;

    const maxClients = Number(formState.maxClients.trim());
    if (!Number.isInteger(maxClients) || maxClients < 1) {
      setFormError('Max clients must be a positive integer.');
      return;
    }

    const portValue = formState.subscriptionPort.trim();
    if (portValue && (!/^\d+$/.test(portValue) || Number(portValue) > 65535)) {
      setFormError('Subscription port must be an integer between 1 and 65535.');
      return;
    }

    setFormError(null);

    const payload: AdminServerUpdatePayload = {
      host: formState.host.trim(),
      location: normalizeOptionalField(formState.location),
      max_clients: maxClients,
      subscription_host: normalizeOptionalField(formState.subscriptionHost),
      subscription_port: normalizeOptionalNumber(formState.subscriptionPort),
      subscription_path: normalizeOptionalField(formState.subscriptionPath),
      inbound_remark: normalizeOptionalField(formState.inboundRemark),
      client_flow: normalizeOptionalField(formState.clientFlow),
    };

    try {
      await updateServer.mutateAsync({ id: editingServer.id, payload });
      closeEditor();
    } catch {
      // Surface API error through mutation state in the modal.
    }
  }

  return (
    <div className="space-y-6">
      <h2 className="text-xl font-bold text-white mb-6">Servers</h2>

      <div className="bg-gray-900 rounded-xl border border-gray-800 overflow-hidden">
        <table className="w-full">
          <thead>
            <tr className="border-b border-gray-800">
              <th className="text-left text-xs font-medium text-gray-500 px-4 py-3">Status</th>
              <th className="text-left text-xs font-medium text-gray-500 px-4 py-3">Name</th>
              <th className="text-left text-xs font-medium text-gray-500 px-4 py-3">Panel Host</th>
              <th className="text-left text-xs font-medium text-gray-500 px-4 py-3">Location</th>
              <th className="text-left text-xs font-medium text-gray-500 px-4 py-3">Profile</th>
              <th className="text-left text-xs font-medium text-gray-500 px-4 py-3">Clients</th>
              <th className="text-left text-xs font-medium text-gray-500 px-4 py-3">Actions</th>
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
                <td className="px-4 py-3 text-sm">
                  <ProfileBadge server={s} />
                </td>
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
                <td className="px-4 py-3">
                  <button
                    onClick={() => openEditor(s)}
                    className="text-xs font-medium px-3 py-2 rounded-lg bg-gray-800 text-gray-200 hover:bg-gray-700 transition-colors"
                  >
                    Configure
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {editingServer && formState && (
        <ServerEditorModal
          server={editingServer}
          formState={formState}
          isSaving={updateServer.isPending}
          error={formError ?? extractErrorText(updateServer.error)}
          onChange={setFormState}
          onClose={closeEditor}
          onSubmit={handleSave}
        />
      )}
    </div>
  );
}

type ServerFormState = {
  host: string;
  location: string;
  maxClients: string;
  subscriptionHost: string;
  subscriptionPort: string;
  subscriptionPath: string;
  inboundRemark: string;
  clientFlow: string;
};

function createFormState(server: AdminServer): ServerFormState {
  return {
    host: server.host,
    location: server.location ?? '',
    maxClients: String(server.max_clients),
    subscriptionHost: server.subscription_host ?? '',
    subscriptionPort: server.subscription_port === null ? '' : String(server.subscription_port),
    subscriptionPath: server.subscription_path ?? '',
    inboundRemark: server.inbound_remark ?? '',
    clientFlow: server.client_flow ?? '',
  };
}

function normalizeOptionalField(value: string): string | null {
  const normalized = value.trim();
  return normalized.length > 0 ? normalized : null;
}

function normalizeOptionalNumber(value: string): number | null {
  const normalized = value.trim();
  if (!normalized) return null;
  return Number(normalized);
}

function hasCustomProfile(server: AdminServer): boolean {
  return Boolean(
    server.subscription_host ||
    server.subscription_port ||
    server.subscription_path ||
    server.inbound_remark ||
    server.client_flow,
  );
}

function extractErrorText(error: unknown): string | null {
  if (error instanceof ApiRequestError) {
    if (typeof error.body === 'object' && error.body !== null && 'error' in error.body) {
      const bodyError = (error.body as { error?: unknown }).error;
      if (typeof bodyError === 'string') return bodyError;
    }
    return `Request failed (${error.status})`;
  }
  if (error instanceof Error) return error.message;
  return null;
}

function ProfileBadge({ server }: { server: AdminServer }) {
  const custom = hasCustomProfile(server);

  return (
    <span
      className={`inline-flex items-center rounded-full px-2.5 py-1 text-xs font-medium ${
        custom ? 'bg-emerald-500/15 text-emerald-300' : 'bg-gray-800 text-gray-400'
      }`}
    >
      {custom ? 'Custom' : 'Default'}
    </span>
  );
}

function ServerEditorModal({
  server,
  formState,
  isSaving,
  error,
  onChange,
  onClose,
  onSubmit,
}: {
  server: AdminServer;
  formState: ServerFormState;
  isSaving: boolean;
  error: string | null;
  onChange: (state: ServerFormState) => void;
  onClose: () => void;
  onSubmit: (event: FormEvent<HTMLFormElement>) => void;
}) {
  function updateField<K extends keyof ServerFormState>(key: K, value: ServerFormState[K]) {
    onChange({ ...formState, [key]: value });
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 px-6">
      <div className="w-full max-w-3xl rounded-2xl border border-gray-800 bg-gray-950 shadow-2xl">
        <div className="flex items-start justify-between border-b border-gray-800 px-6 py-5">
          <div>
            <h3 className="text-lg font-semibold text-white">{server.name}</h3>
            <p className="mt-1 text-sm text-gray-400">
              Configure a server-specific transport profile. Leave optional fields empty to keep global defaults.
            </p>
          </div>
          <button
            onClick={onClose}
            className="rounded-lg px-3 py-2 text-sm text-gray-400 hover:bg-gray-900 hover:text-white transition-colors"
          >
            Close
          </button>
        </div>

        <form onSubmit={onSubmit} className="space-y-5 px-6 py-6">
          <div className="grid grid-cols-2 gap-4">
            <LabeledInput
              label="Panel host"
              value={formState.host}
              onChange={(value) => updateField('host', value)}
              placeholder="https://panel.example.com"
              required
            />
            <LabeledInput
              label="Location"
              value={formState.location}
              onChange={(value) => updateField('location', value)}
              placeholder="Saint Petersburg"
            />
            <LabeledInput
              label="Max clients"
              value={formState.maxClients}
              onChange={(value) => updateField('maxClients', value)}
              placeholder="1000"
              inputMode="numeric"
              required
            />
            <LabeledInput
              label="Subscription host"
              value={formState.subscriptionHost}
              onChange={(value) => updateField('subscriptionHost', value)}
              placeholder="https://spb.example.com"
            />
            <LabeledInput
              label="Subscription port"
              value={formState.subscriptionPort}
              onChange={(value) => updateField('subscriptionPort', value)}
              placeholder="443"
              inputMode="numeric"
            />
            <LabeledInput
              label="Subscription path"
              value={formState.subscriptionPath}
              onChange={(value) => updateField('subscriptionPath', value)}
              placeholder="/user/"
            />
            <LabeledInput
              label="Inbound remark"
              value={formState.inboundRemark}
              onChange={(value) => updateField('inboundRemark', value)}
              placeholder="spb-reality"
            />
            <LabeledInput
              label="Client flow"
              value={formState.clientFlow}
              onChange={(value) => updateField('clientFlow', value)}
              placeholder="xtls-rprx-vision"
            />
          </div>

          {error && (
            <div className="rounded-xl border border-red-500/30 bg-red-500/10 px-4 py-3 text-sm text-red-200">
              {error}
            </div>
          )}

          <div className="flex items-center justify-between border-t border-gray-800 pt-5">
            <div className="text-xs text-gray-500">
              Use custom `inbound_remark` and `client_flow` for the direct SPB REALITY profile. Amsterdam can stay on defaults.
            </div>
            <div className="flex items-center gap-3">
              <button
                type="button"
                onClick={onClose}
                className="rounded-lg px-4 py-2 text-sm font-medium text-gray-300 hover:bg-gray-900 transition-colors"
              >
                Cancel
              </button>
              <button
                type="submit"
                disabled={isSaving}
                className="rounded-lg bg-indigo-600 px-4 py-2 text-sm font-medium text-white hover:bg-indigo-700 disabled:opacity-60 transition-colors"
              >
                {isSaving ? 'Saving...' : 'Save changes'}
              </button>
            </div>
          </div>
        </form>
      </div>
    </div>
  );
}

function LabeledInput({
  label,
  value,
  onChange,
  placeholder,
  inputMode,
  required = false,
}: {
  label: string;
  value: string;
  onChange: (value: string) => void;
  placeholder: string;
  inputMode?: HTMLAttributes<HTMLInputElement>['inputMode'];
  required?: boolean;
}) {
  return (
    <label className="block">
      <span className="mb-2 block text-xs font-medium uppercase tracking-wide text-gray-500">
        {label}
      </span>
      <input
        value={value}
        onChange={(event) => onChange(event.target.value)}
        placeholder={placeholder}
        inputMode={inputMode}
        required={required}
        className="w-full rounded-xl border border-gray-800 bg-gray-900 px-4 py-3 text-sm text-white outline-none transition-colors placeholder:text-gray-600 focus:border-indigo-500"
      />
    </label>
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
