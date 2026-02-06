import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { useNavigate } from 'react-router-dom';
import { listsApi } from '../api/client';
import type { List } from '../api/client';
import './Lists.css';

export default function Lists() {
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [newListName, setNewListName] = useState('');
  const [newListDescription, setNewListDescription] = useState('');
  const [newListType, setNewListType] = useState('mixed');
  const [newListTags, setNewListTags] = useState('');
  const [createError, setCreateError] = useState('');

  const navigate = useNavigate();
  const queryClient = useQueryClient();

  const { data: lists, isLoading, error } = useQuery({
    queryKey: ['lists'],
    queryFn: async () => {
      const response = await listsApi.getAll();
      return response.data;
    },
  });

  const createMutation = useMutation({
    mutationFn: async (data: { name: string; description?: string; list_type?: string; tags?: string[] }) => {
      const response = await listsApi.create(data);
      return response.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['lists'] });
      setShowCreateModal(false);
      setNewListName('');
      setNewListDescription('');
      setNewListType('mixed');
      setNewListTags('');
      setCreateError('');
    },
    onError: (err: unknown) => {
      const error = err as { response?: { data?: { detail?: string } } };
      setCreateError(error.response?.data?.detail || 'Failed to create list');
    },
  });

  const handleCreateList = (e: React.FormEvent) => {
    e.preventDefault();
    const tags = newListTags
      .split(',')
      .map((t) => t.trim())
      .filter((t) => t.length > 0);

    createMutation.mutate({
      name: newListName,
      description: newListDescription || undefined,
      list_type: newListType,
      tags: tags.length > 0 ? tags : undefined,
    });
  };

  const handleRowClick = (list: List) => {
    navigate(`/lists/${list.slug}`);
  };

  if (error) {
    return (
      <div className="lists-page">
        <header className="page-header">
          <h1 className="page-title">Lists</h1>
        </header>
        <div className="alert alert-error">
          [ERROR] Failed to load lists. Check connection and try again.
        </div>
      </div>
    );
  }

  return (
    <div className="lists-page">
      <header className="page-header">
        <div className="flex justify-between items-center">
          <div>
            <h1 className="page-title">Lists</h1>
            <p className="page-subtitle">Manage External Dynamic Lists for firewall integration</p>
          </div>
          <button className="btn btn-primary" onClick={() => setShowCreateModal(true)}>
            + NEW LIST
          </button>
        </div>
      </header>

      <div className="panel">
        {isLoading ? (
          <div className="loading-container">
            <div className="loading-spinner"></div>
            <span className="text-muted">Loading lists...</span>
          </div>
        ) : lists && lists.length > 0 ? (
          <table className="data-table">
            <thead>
              <tr>
                <th>Name</th>
                <th>Slug</th>
                <th>Type</th>
                <th>IOCs</th>
                <th>Tags</th>
                <th>Created</th>
                <th>Status</th>
              </tr>
            </thead>
            <tbody>
              {lists.map((list) => (
                <tr key={list.id} className="clickable" onClick={() => handleRowClick(list)}>
                  <td>
                    <span className="list-name">{list.name}</span>
                  </td>
                  <td>
                    <code className="list-slug">{list.slug}</code>
                  </td>
                  <td>
                    <span className="list-type-badge">{(list.list_type || 'mixed').toUpperCase()}</span>
                  </td>
                  <td>
                    <span className="badge">{list.ioc_count || 0}</span>
                  </td>
                  <td>
                    <div className="tags-cell">
                      {list.tags?.slice(0, 3).map((tag) => (
                        <span key={tag} className="tag">{tag}</span>
                      ))}
                      {list.tags && list.tags.length > 3 && (
                        <span className="tag-overflow">+{list.tags.length - 3}</span>
                      )}
                    </div>
                  </td>
                  <td>
                    <span className="text-muted text-sm">
                      {new Date(list.created_at).toLocaleDateString()}
                    </span>
                  </td>
                  <td>
                    <span className="status-dot active" title="Active"></span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        ) : (
          <div className="empty-state">
            <div className="empty-state-icon">[]</div>
            <p className="empty-state-title">No lists found</p>
            <p className="empty-state-description">
              Create your first list to start building External Dynamic Lists
            </p>
            <button className="btn btn-primary mt-lg" onClick={() => setShowCreateModal(true)}>
              + CREATE FIRST LIST
            </button>
          </div>
        )}
      </div>

      {/* Create List Modal */}
      {showCreateModal && (
        <div className="modal-overlay" onClick={() => setShowCreateModal(false)}>
          <div className="modal-content" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <h3 className="modal-title">Create New List</h3>
              <button className="modal-close" onClick={() => setShowCreateModal(false)}>
                &times;
              </button>
            </div>

            <form onSubmit={handleCreateList}>
              {createError && (
                <div className="alert alert-error mb-md">
                  [ERROR] {createError}
                </div>
              )}

              <div className="form-group">
                <label htmlFor="list-name">List Name *</label>
                <input
                  id="list-name"
                  type="text"
                  value={newListName}
                  onChange={(e) => setNewListName(e.target.value)}
                  placeholder="e.g., Malicious IPs"
                  required
                />
                <span className="form-hint">
                  A slug will be auto-generated from the name
                </span>
              </div>

              <div className="form-group">
                <label htmlFor="list-description">Description</label>
                <textarea
                  id="list-description"
                  value={newListDescription}
                  onChange={(e) => setNewListDescription(e.target.value)}
                  placeholder="Optional description of this list's purpose"
                  rows={3}
                />
              </div>

              <div className="form-group">
                <label htmlFor="list-type">List Type</label>
                <select
                  id="list-type"
                  value={newListType}
                  onChange={(e) => setNewListType(e.target.value)}
                >
                  <option value="mixed">Mixed</option>
                  <option value="ip">IP/CIDR</option>
                  <option value="domain">Domain</option>
                  <option value="hash">Hash</option>
                </select>
                <span className="form-hint">
                  Restricts which IOC types can be added
                </span>
              </div>

              <div className="form-group">
                <label htmlFor="list-tags">Tags</label>
                <input
                  id="list-tags"
                  type="text"
                  value={newListTags}
                  onChange={(e) => setNewListTags(e.target.value)}
                  placeholder="e.g., malware, botnet, c2 (comma-separated)"
                />
              </div>

              <div className="flex gap-md justify-end">
                <button
                  type="button"
                  className="btn btn-secondary"
                  onClick={() => setShowCreateModal(false)}
                >
                  CANCEL
                </button>
                <button
                  type="submit"
                  className="btn btn-primary"
                  disabled={createMutation.isPending || !newListName}
                >
                  {createMutation.isPending ? 'CREATING...' : 'CREATE LIST'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
