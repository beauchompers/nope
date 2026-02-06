import { useState, useEffect } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import api, { settingsApi } from '../api/client';
import type { APIKey } from '../api/client';
import ConfirmModal from '../components/ConfirmModal';
import './Settings.css';

interface User {
  id: number;
  username: string;
  role: 'admin' | 'analyst';
}

interface Credential {
  id: number;
  username: string;
}

interface Exclusion {
  id: number;
  value: string;
  type: string;
  reason: string | null;
  is_builtin: boolean;
}

// Helper function for relative time formatting
function formatRelativeTime(dateString: string | null): string {
  if (!dateString) return 'Never';

  const date = new Date(dateString);
  const now = new Date();
  const diffMs = now.getTime() - date.getTime();
  const diffSec = Math.floor(diffMs / 1000);
  const diffMin = Math.floor(diffSec / 60);
  const diffHour = Math.floor(diffMin / 60);
  const diffDay = Math.floor(diffHour / 24);

  if (diffSec < 60) return 'Just now';
  if (diffMin < 60) return `${diffMin} minute${diffMin !== 1 ? 's' : ''} ago`;
  if (diffHour < 24) return `${diffHour} hour${diffHour !== 1 ? 's' : ''} ago`;
  if (diffDay < 30) return `${diffDay} day${diffDay !== 1 ? 's' : ''} ago`;

  return date.toLocaleDateString();
}

export default function Settings() {
  const queryClient = useQueryClient();

  // Users state
  const [showAddUser, setShowAddUser] = useState(false);
  const [newUsername, setNewUsername] = useState('');
  const [newPassword, setNewPassword] = useState('');
  const [newRole, setNewRole] = useState<'admin' | 'analyst'>('analyst');
  const [userError, setUserError] = useState('');
  const [userToEdit, setUserToEdit] = useState<User | null>(null);
  const [editRole, setEditRole] = useState<'admin' | 'analyst'>('analyst');
  const [editPassword, setEditPassword] = useState('');
  const [editUserError, setEditUserError] = useState('');

  // EDL Credential state
  const [showChangeCredential, setShowChangeCredential] = useState(false);
  const [credUsername, setCredUsername] = useState('');
  const [credPassword, setCredPassword] = useState('');
  const [credError, setCredError] = useState('');

  // Exclusions state
  const [showAddExclusion, setShowAddExclusion] = useState(false);
  const [newExclusionValue, setNewExclusionValue] = useState('');
  const [newExclusionType, setNewExclusionType] = useState('domain');
  const [newExclusionReason, setNewExclusionReason] = useState('');
  const [exclusionError, setExclusionError] = useState('');

  // API Keys state
  const [showAddApiKey, setShowAddApiKey] = useState(false);
  const [newApiKeyName, setNewApiKeyName] = useState('');
  const [apiKeyError, setApiKeyError] = useState('');
  const [copiedKeyId, setCopiedKeyId] = useState<number | null>(null);

  // Deletion confirmation state
  const [userToDelete, setUserToDelete] = useState<User | null>(null);
  const [exclusionToDelete, setExclusionToDelete] = useState<Exclusion | null>(null);
  const [apiKeyToDelete, setApiKeyToDelete] = useState<APIKey | null>(null);
  const [userDeleteError, setUserDeleteError] = useState('');
  const [exclusionDeleteError, setExclusionDeleteError] = useState('');
  const [apiKeyDeleteError, setApiKeyDeleteError] = useState('');

  // EDL URL state
  const [edlHost, setEdlHost] = useState('');
  const [edlPort, setEdlPort] = useState(8081);
  const [edlUrlError, setEdlUrlError] = useState('');
  const [edlUrlSuccess, setEdlUrlSuccess] = useState(false);

  // Queries
  const { data: users } = useQuery({
    queryKey: ['settings-users'],
    queryFn: async () => {
      const response = await api.get<User[]>('/settings/users');
      return response.data;
    },
  });

  const { data: credential } = useQuery({
    queryKey: ['settings-credential'],
    queryFn: async () => {
      const response = await api.get<Credential>('/settings/credential');
      return response.data;
    },
  });

  const { data: exclusions } = useQuery({
    queryKey: ['settings-exclusions'],
    queryFn: async () => {
      const response = await api.get<Exclusion[]>('/settings/exclusions');
      return response.data;
    },
  });

  const { data: apiKeys } = useQuery({
    queryKey: ['settings-api-keys'],
    queryFn: async () => {
      const response = await settingsApi.getApiKeys();
      return response.data;
    },
  });

  const { data: edlUrlConfig } = useQuery({
    queryKey: ['settings-edl-url'],
    queryFn: async () => {
      const response = await settingsApi.getEdlUrl();
      return response.data;
    },
  });

  // Initialize EDL URL form when data loads
  useEffect(() => {
    if (edlUrlConfig) {
      setEdlHost(edlUrlConfig.host);
      setEdlPort(edlUrlConfig.port);
    }
  }, [edlUrlConfig]);

  // Pre-fill credential form when opening modal
  useEffect(() => {
    if (showChangeCredential && credential) {
      setCredUsername(credential.username);
      setCredPassword('');
      setCredError('');
    }
  }, [showChangeCredential, credential]);

  // User mutations
  const createUserMutation = useMutation({
    mutationFn: async (data: { username: string; password: string; role: string }) => {
      await api.post('/settings/users', data);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['settings-users'] });
      setShowAddUser(false);
      setNewUsername('');
      setNewPassword('');
      setNewRole('analyst');
      setUserError('');
    },
    onError: (err: unknown) => {
      const error = err as { response?: { data?: { detail?: string } } };
      setUserError(error.response?.data?.detail || 'Failed to create user');
    },
  });

  const updateUserMutation = useMutation({
    mutationFn: async ({ userId, data }: { userId: number; data: { role?: string; password?: string } }) => {
      await api.patch(`/settings/users/${userId}`, data);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['settings-users'] });
      setUserToEdit(null);
      setEditPassword('');
      setEditUserError('');
    },
    onError: (err: unknown) => {
      const error = err as { response?: { data?: { detail?: string } } };
      setEditUserError(error.response?.data?.detail || 'Failed to update user');
    },
  });

  const deleteUserMutation = useMutation({
    mutationFn: async (userId: number) => {
      await api.delete(`/settings/users/${userId}`);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['settings-users'] });
      setUserToDelete(null);
      setUserDeleteError('');
    },
    onError: (err: unknown) => {
      const error = err as { response?: { data?: { detail?: string } } };
      setUserDeleteError(error.response?.data?.detail || 'Failed to delete user');
    },
  });

  // EDL Credential mutation
  const updateCredentialMutation = useMutation({
    mutationFn: async (data: { username: string; password?: string }) => {
      await api.put('/settings/credential', data);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['settings-credential'] });
      setShowChangeCredential(false);
      setCredUsername('');
      setCredPassword('');
      setCredError('');
    },
    onError: (err: unknown) => {
      const error = err as { response?: { data?: { detail?: string } } };
      setCredError(error.response?.data?.detail || 'Failed to update credential');
    },
  });

  // Exclusion mutations
  const createExclusionMutation = useMutation({
    mutationFn: async (data: { value: string; type: string; reason?: string }) => {
      await api.post('/settings/exclusions', data);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['settings-exclusions'] });
      setShowAddExclusion(false);
      setNewExclusionValue('');
      setNewExclusionType('domain');
      setNewExclusionReason('');
      setExclusionError('');
    },
    onError: (err: unknown) => {
      const error = err as { response?: { data?: { detail?: string } } };
      setExclusionError(error.response?.data?.detail || 'Failed to create exclusion');
    },
  });

  const deleteExclusionMutation = useMutation({
    mutationFn: async (exclusionId: number) => {
      await api.delete(`/settings/exclusions/${exclusionId}`);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['settings-exclusions'] });
      setExclusionToDelete(null);
      setExclusionDeleteError('');
    },
    onError: (err: unknown) => {
      const error = err as { response?: { data?: { detail?: string } } };
      setExclusionDeleteError(error.response?.data?.detail || 'Failed to delete exclusion');
    },
  });

  // API Key mutations
  const createApiKeyMutation = useMutation({
    mutationFn: async (name: string) => {
      const response = await settingsApi.createApiKey(name);
      return response.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['settings-api-keys'] });
      setShowAddApiKey(false);
      setNewApiKeyName('');
      setApiKeyError('');
    },
    onError: (err: unknown) => {
      const error = err as { response?: { data?: { detail?: string } } };
      setApiKeyError(error.response?.data?.detail || 'Failed to create API key');
    },
  });

  const deleteApiKeyMutation = useMutation({
    mutationFn: async (apiKeyId: number) => {
      await settingsApi.deleteApiKey(apiKeyId);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['settings-api-keys'] });
      setApiKeyToDelete(null);
      setApiKeyDeleteError('');
    },
    onError: (err: unknown) => {
      const error = err as { response?: { data?: { detail?: string } } };
      setApiKeyDeleteError(error.response?.data?.detail || 'Failed to delete API key');
    },
  });

  // EDL URL mutation
  const updateEdlUrlMutation = useMutation({
    mutationFn: async (data: { host: string; port: number }) => {
      const response = await settingsApi.updateEdlUrl(data);
      return response.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['settings-edl-url'] });
      queryClient.invalidateQueries({ queryKey: ['settings-config'] });
      setEdlUrlError('');
      setEdlUrlSuccess(true);
      setTimeout(() => setEdlUrlSuccess(false), 3000);
    },
    onError: (err: unknown) => {
      const error = err as { response?: { data?: { detail?: string } } };
      setEdlUrlError(error.response?.data?.detail || 'Failed to update EDL URL');
      setEdlUrlSuccess(false);
    },
  });

  const handleSaveCredential = () => {
    const data: { username: string; password?: string } = { username: credUsername };
    if (credPassword) {
      data.password = credPassword;
    }
    updateCredentialMutation.mutate(data);
  };

  const handleCopyApiKey = async (apiKey: APIKey) => {
    try {
      await navigator.clipboard.writeText(apiKey.key);
      setCopiedKeyId(apiKey.id);
      setTimeout(() => setCopiedKeyId(null), 2000);
    } catch {
      // Fallback for older browsers
      const textArea = document.createElement('textarea');
      textArea.value = apiKey.key;
      document.body.appendChild(textArea);
      textArea.select();
      document.execCommand('copy');
      document.body.removeChild(textArea);
      setCopiedKeyId(apiKey.id);
      setTimeout(() => setCopiedKeyId(null), 2000);
    }
  };

  const truncateApiKey = (key: string): string => {
    if (key.length <= 20) return key;
    return key.substring(0, 20) + '...';
  };

  return (
    <div className="settings-page">
      <header className="page-header">
        <h1 className="page-title">Settings</h1>
        <p className="page-subtitle">Manage users, EDL credential, and exclusions</p>
      </header>

      {/* EDL URL Configuration Section */}
      <section className="settings-section">
        <h3 className="section-title">EDL URL Configuration</h3>
        <p className="section-description">
          Configure the base URL for EDL links displayed in the UI and MCP tools
        </p>

        <div className="panel">
          {edlUrlError && <div className="alert alert-error mb-md">{edlUrlError}</div>}
          {edlUrlSuccess && <div className="alert alert-success mb-md">EDL URL updated successfully</div>}

          <div className="edl-url-form">
            <div className="form-row-inline">
              <div className="form-group">
                <label htmlFor="edl-host">Host</label>
                <input
                  id="edl-host"
                  type="text"
                  value={edlHost}
                  onChange={(e) => setEdlHost(e.target.value)}
                  placeholder="e.g., 192.168.1.50 or nope-server"
                />
              </div>
              <div className="form-group" style={{ width: '120px' }}>
                <label htmlFor="edl-port">Port</label>
                <input
                  id="edl-port"
                  type="number"
                  min={1}
                  max={65535}
                  value={edlPort}
                  onChange={(e) => setEdlPort(parseInt(e.target.value) || 8081)}
                />
              </div>
            </div>

            <div className="edl-url-preview">
              <span className="preview-label">Preview:</span>
              <code className="preview-url">https://{edlHost || 'localhost'}:{edlPort}</code>
            </div>

            <button
              className="btn btn-primary"
              onClick={() => updateEdlUrlMutation.mutate({ host: edlHost, port: edlPort })}
              disabled={!edlHost || updateEdlUrlMutation.isPending}
            >
              {updateEdlUrlMutation.isPending ? 'SAVING...' : 'SAVE'}
            </button>
          </div>
        </div>
      </section>

      {/* UI Users Section */}
      <section className="settings-section">
        <div className="section-header">
          <h3 className="section-title">UI Users</h3>
          <button className="btn btn-primary btn-sm" onClick={() => setShowAddUser(true)}>
            + ADD USER
          </button>
        </div>
        <p className="section-description">Users who can log in to the web interface</p>

        <div className="panel">
          <table className="data-table">
            <thead>
              <tr>
                <th>Username</th>
                <th>Role</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {users?.map((user) => (
                <tr key={user.id}>
                  <td><code>{user.username}</code></td>
                  <td>
                    <span className={`badge ${user.role === 'admin' ? 'badge-admin' : 'badge-analyst'}`}>
                      {user.role}
                    </span>
                  </td>
                  <td>
                    <button
                      className="btn btn-secondary btn-sm"
                      onClick={() => {
                        setUserToEdit(user);
                        setEditRole(user.role);
                        setEditPassword('');
                        setEditUserError('');
                      }}
                      style={{ marginRight: '0.5rem' }}
                    >
                      EDIT
                    </button>
                    <button
                      className="btn btn-danger btn-sm"
                      onClick={() => setUserToDelete(user)}
                    >
                      DELETE
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        {showAddUser && (
          <div className="inline-form">
            {userError && <div className="alert alert-error mb-sm">{userError}</div>}
            <div className="form-row">
              <input
                type="text"
                placeholder="Username"
                value={newUsername}
                onChange={(e) => setNewUsername(e.target.value)}
              />
              <input
                type="password"
                placeholder="Password (min 12 chars)"
                value={newPassword}
                onChange={(e) => setNewPassword(e.target.value)}
              />
              <select
                value={newRole}
                onChange={(e) => setNewRole(e.target.value as 'admin' | 'analyst')}
              >
                <option value="analyst">Analyst</option>
                <option value="admin">Admin</option>
              </select>
              <button
                className="btn btn-primary"
                onClick={() => createUserMutation.mutate({ username: newUsername, password: newPassword, role: newRole })}
                disabled={!newUsername || !newPassword}
              >
                CREATE
              </button>
              <button className="btn btn-secondary" onClick={() => {
                setShowAddUser(false);
                setNewUsername('');
                setNewPassword('');
                setNewRole('analyst');
                setUserError('');
              }}>
                CANCEL
              </button>
            </div>
          </div>
        )}
      </section>

      {/* EDL Credential Section */}
      <section className="settings-section">
        <h3 className="section-title">EDL Credential</h3>
        <p className="section-description">Credential used by firewalls to authenticate when fetching EDL files</p>

        <div className="panel credential-panel">
          <div className="credential-display">
            <div className="credential-row">
              <span className="credential-label">USERNAME</span>
              <code className="credential-value">{credential?.username || '—'}</code>
            </div>
            <div className="credential-row">
              <span className="credential-label">PASSWORD</span>
              <span className="credential-value password-dots">••••••••</span>
            </div>
          </div>
          <button
            className="btn btn-secondary"
            onClick={() => setShowChangeCredential(true)}
          >
            CHANGE
          </button>
        </div>
      </section>

      {/* API Keys Section */}
      <section className="settings-section">
        <div className="section-header">
          <h3 className="section-title">API Keys</h3>
          <button className="btn btn-primary btn-sm" onClick={() => setShowAddApiKey(true)}>
            + ADD API KEY
          </button>
        </div>
        <p className="section-description">API keys for MCP server authentication</p>

        <div className="panel">
          <table className="data-table">
            <thead>
              <tr>
                <th>Name</th>
                <th>Key</th>
                <th>Last Used</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {apiKeys?.length === 0 && (
                <tr>
                  <td colSpan={4} className="text-muted text-center">No API keys configured</td>
                </tr>
              )}
              {apiKeys?.map((apiKey) => (
                <tr key={apiKey.id}>
                  <td><code>{apiKey.name}</code></td>
                  <td>
                    <span
                      className="api-key-value"
                      onClick={() => handleCopyApiKey(apiKey)}
                      onKeyDown={(e) => {
                        if (e.key === 'Enter' || e.key === ' ') {
                          e.preventDefault();
                          handleCopyApiKey(apiKey);
                        }
                      }}
                      role="button"
                      tabIndex={0}
                      title="Click to copy full key"
                    >
                      <code>{truncateApiKey(apiKey.key)}</code>
                      <span className="copy-indicator">
                        {copiedKeyId === apiKey.id ? 'Copied!' : 'Click to copy'}
                      </span>
                    </span>
                  </td>
                  <td className="text-muted">{formatRelativeTime(apiKey.last_used_at)}</td>
                  <td>
                    <button
                      className="btn btn-danger btn-sm"
                      onClick={() => setApiKeyToDelete(apiKey)}
                    >
                      DELETE
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        {showAddApiKey && (
          <div className="inline-form">
            {apiKeyError && <div className="alert alert-error mb-sm">{apiKeyError}</div>}
            <div className="form-row">
              <input
                type="text"
                placeholder="API Key Name (e.g., mcp-server-prod)"
                value={newApiKeyName}
                onChange={(e) => setNewApiKeyName(e.target.value)}
              />
              <button
                className="btn btn-primary"
                onClick={() => createApiKeyMutation.mutate(newApiKeyName)}
                disabled={!newApiKeyName || createApiKeyMutation.isPending}
              >
                {createApiKeyMutation.isPending ? 'CREATING...' : 'CREATE'}
              </button>
              <button className="btn btn-secondary" onClick={() => {
                setShowAddApiKey(false);
                setNewApiKeyName('');
                setApiKeyError('');
              }}>
                CANCEL
              </button>
            </div>
          </div>
        )}
      </section>

      {/* Exclusions Section */}
      <section className="settings-section">
        <div className="section-header">
          <h3 className="section-title">Exclusions</h3>
          <button className="btn btn-primary btn-sm" onClick={() => setShowAddExclusion(true)}>
            + ADD EXCLUSION
          </button>
        </div>
        <p className="section-description">Values that cannot be added as IOCs (TLDs, private IPs, etc.)</p>

        <div className="panel">
          <table className="data-table">
            <thead>
              <tr>
                <th>Value</th>
                <th>Type</th>
                <th>Reason</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {exclusions?.map((excl) => (
                <tr key={excl.id}>
                  <td><code>{excl.value}</code></td>
                  <td><span className="badge">{excl.type}</span></td>
                  <td className="text-muted">{excl.reason || '-'}</td>
                  <td>
                    {excl.is_builtin ? (
                      <span className="text-muted text-sm">Built-in</span>
                    ) : (
                      <button
                        className="btn btn-danger btn-sm"
                        onClick={() => setExclusionToDelete(excl)}
                      >
                        DELETE
                      </button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        {showAddExclusion && (
          <div className="inline-form">
            {exclusionError && <div className="alert alert-error mb-sm">{exclusionError}</div>}
            <div className="form-row">
              <input
                type="text"
                placeholder="Value (e.g., example.com or *.example.com)"
                value={newExclusionValue}
                onChange={(e) => {
                  const val = e.target.value;
                  setNewExclusionValue(val);
                  // Auto-detect wildcard patterns
                  if (val.startsWith('*.')) {
                    setNewExclusionType('wildcard');
                  }
                }}
              />
              <select
                value={newExclusionType}
                onChange={(e) => setNewExclusionType(e.target.value)}
              >
                <option value="domain">Domain</option>
                <option value="ip">IP</option>
                <option value="cidr">CIDR</option>
                <option value="wildcard">Wildcard</option>
              </select>
              <input
                type="text"
                placeholder="Reason (optional)"
                value={newExclusionReason}
                onChange={(e) => setNewExclusionReason(e.target.value)}
              />
              <button
                className="btn btn-primary"
                onClick={() => createExclusionMutation.mutate({
                  value: newExclusionValue,
                  type: newExclusionType,
                  reason: newExclusionReason || undefined,
                })}
                disabled={!newExclusionValue}
              >
                CREATE
              </button>
              <button className="btn btn-secondary" onClick={() => setShowAddExclusion(false)}>
                CANCEL
              </button>
            </div>
          </div>
        )}
      </section>

      {/* Delete User Confirmation */}
      {userToDelete && (
        <ConfirmModal
          title="Delete User"
          message={`Are you sure you want to delete user "${userToDelete.username}"? This action cannot be undone.`}
          confirmText="DELETE"
          variant="danger"
          onConfirm={() => deleteUserMutation.mutate(userToDelete.id)}
          onCancel={() => {
            setUserToDelete(null);
            setUserDeleteError('');
          }}
          isLoading={deleteUserMutation.isPending}
          error={userDeleteError}
        />
      )}

      {/* Edit User Modal */}
      {userToEdit && (
        <div className="modal-overlay" onClick={() => setUserToEdit(null)}>
          <div className="modal-content" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <h2 className="modal-title">Edit User: {userToEdit.username}</h2>
              <button className="modal-close" onClick={() => setUserToEdit(null)}>
                &times;
              </button>
            </div>

            {editUserError && <div className="alert alert-error mb-md">{editUserError}</div>}

            <div className="form-group">
              <label htmlFor="edit-role">Role</label>
              <select
                id="edit-role"
                value={editRole}
                onChange={(e) => setEditRole(e.target.value as 'admin' | 'analyst')}
              >
                <option value="analyst">Analyst</option>
                <option value="admin">Admin</option>
              </select>
              <span className="form-hint">Admin: full access. Analyst: IOC management only.</span>
            </div>

            <div className="form-group">
              <label htmlFor="edit-password">New Password</label>
              <input
                id="edit-password"
                type="password"
                value={editPassword}
                onChange={(e) => setEditPassword(e.target.value)}
                placeholder="Leave blank to keep current password"
              />
              <span className="form-hint">Min 12 chars, uppercase, lowercase, digit required</span>
            </div>

            <div className="modal-actions">
              <button
                className="btn btn-secondary"
                onClick={() => setUserToEdit(null)}
              >
                CANCEL
              </button>
              <button
                className="btn btn-primary"
                onClick={() => {
                  const data: { role?: string; password?: string } = {};
                  if (editRole !== userToEdit.role) {
                    data.role = editRole;
                  }
                  if (editPassword) {
                    data.password = editPassword;
                  }
                  if (Object.keys(data).length > 0) {
                    updateUserMutation.mutate({ userId: userToEdit.id, data });
                  } else {
                    setUserToEdit(null);
                  }
                }}
                disabled={updateUserMutation.isPending}
              >
                {updateUserMutation.isPending ? 'SAVING...' : 'SAVE CHANGES'}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Change Credential Modal */}
      {showChangeCredential && (
        <div className="modal-overlay" onClick={() => setShowChangeCredential(false)}>
          <div className="modal-content" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <h2 className="modal-title">Change EDL Credential</h2>
              <button className="modal-close" onClick={() => setShowChangeCredential(false)}>
                &times;
              </button>
            </div>

            {credError && <div className="alert alert-error mb-md">{credError}</div>}

            <div className="form-group">
              <label htmlFor="cred-username">Username</label>
              <input
                id="cred-username"
                type="text"
                value={credUsername}
                onChange={(e) => setCredUsername(e.target.value)}
                placeholder="Username for EDL access"
              />
            </div>

            <div className="form-group">
              <label htmlFor="cred-password">New Password</label>
              <input
                id="cred-password"
                type="password"
                value={credPassword}
                onChange={(e) => setCredPassword(e.target.value)}
                placeholder="Leave blank to keep current password"
              />
              <span className="form-hint">Leave blank to keep the current password</span>
            </div>

            <div className="modal-actions">
              <button
                className="btn btn-secondary"
                onClick={() => setShowChangeCredential(false)}
              >
                CANCEL
              </button>
              <button
                className="btn btn-primary"
                onClick={handleSaveCredential}
                disabled={!credUsername || updateCredentialMutation.isPending}
              >
                {updateCredentialMutation.isPending ? 'SAVING...' : 'SAVE CHANGES'}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Delete Exclusion Confirmation */}
      {exclusionToDelete && (
        <ConfirmModal
          title="Delete Exclusion"
          message={`Are you sure you want to delete exclusion "${exclusionToDelete.value}"? This may allow previously blocked values to be added as IOCs.`}
          confirmText="DELETE"
          variant="danger"
          onConfirm={() => deleteExclusionMutation.mutate(exclusionToDelete.id)}
          onCancel={() => {
            setExclusionToDelete(null);
            setExclusionDeleteError('');
          }}
          isLoading={deleteExclusionMutation.isPending}
          error={exclusionDeleteError}
        />
      )}

      {/* Delete API Key Confirmation */}
      {apiKeyToDelete && (
        <ConfirmModal
          title="Delete API Key"
          message={`Are you sure you want to delete API key "${apiKeyToDelete.name}"? Any services using this key will lose access.`}
          confirmText="DELETE"
          variant="danger"
          onConfirm={() => deleteApiKeyMutation.mutate(apiKeyToDelete.id)}
          onCancel={() => {
            setApiKeyToDelete(null);
            setApiKeyDeleteError('');
          }}
          isLoading={deleteApiKeyMutation.isPending}
          error={apiKeyDeleteError}
        />
      )}
    </div>
  );
}
