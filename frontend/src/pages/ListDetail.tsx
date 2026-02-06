import { useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { listsApi, iocsApi, settingsApi } from '../api/client';
import type { IOC } from '../api/client';
import ConfirmModal from '../components/ConfirmModal';
import './ListDetail.css';

export default function ListDetail() {
  const { slug } = useParams<{ slug: string }>();
  const navigate = useNavigate();
  const queryClient = useQueryClient();

  const [newIocValue, setNewIocValue] = useState('');
  const [newIocComment, setNewIocComment] = useState('');
  const [addError, setAddError] = useState('');
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);
  const [showEditModal, setShowEditModal] = useState(false);
  const [editName, setEditName] = useState('');
  const [editDescription, setEditDescription] = useState('');
  const [editTags, setEditTags] = useState('');
  const [editListType, setEditListType] = useState('');
  const [editError, setEditError] = useState('');
  const [copiedUrl, setCopiedUrl] = useState(false);
  const [iocToRemove, setIocToRemove] = useState<IOC | null>(null);

  // Fetch list details
  const { data: list, isLoading: listLoading, error: listError } = useQuery({
    queryKey: ['list', slug],
    queryFn: async () => {
      const response = await listsApi.get(slug!);
      return response.data;
    },
    enabled: !!slug,
  });

  // Fetch IOCs in the list
  const { data: iocs, isLoading: iocsLoading } = useQuery({
    queryKey: ['list-iocs', slug],
    queryFn: async () => {
      const response = await listsApi.getIOCs(slug!);
      return response.data;
    },
    enabled: !!slug,
  });

  // Fetch config for EDL URL
  const { data: config } = useQuery({
    queryKey: ['config'],
    queryFn: async () => {
      const response = await settingsApi.getConfig();
      return response.data;
    },
    staleTime: 5 * 60 * 1000, // Cache for 5 minutes
  });

  // Add IOC mutation
  const addIocMutation = useMutation({
    mutationFn: async (data: { value: string; comment?: string }) => {
      const response = await iocsApi.create({
        value: data.value,
        list_slugs: [slug!],
        comment: data.comment,
      });
      return response.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['list-iocs', slug] });
      queryClient.invalidateQueries({ queryKey: ['list', slug] });
      queryClient.invalidateQueries({ queryKey: ['lists'] });
      setNewIocValue('');
      setNewIocComment('');
      setAddError('');
    },
    onError: (err: unknown) => {
      const error = err as { response?: { data?: { detail?: string } } };
      setAddError(error.response?.data?.detail || 'Failed to add IOC');
    },
  });

  // Remove IOC from list mutation
  const removeIocMutation = useMutation({
    mutationFn: async (iocId: number) => {
      await iocsApi.removeFromList(iocId, slug!);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['list-iocs', slug] });
      queryClient.invalidateQueries({ queryKey: ['list', slug] });
      queryClient.invalidateQueries({ queryKey: ['lists'] });
    },
  });

  // Update list mutation
  const updateListMutation = useMutation({
    mutationFn: async (data: { name?: string; description?: string; list_type?: string; tags?: string[] }) => {
      const response = await listsApi.update(slug!, data);
      return response.data;
    },
    onSuccess: (updatedList) => {
      queryClient.invalidateQueries({ queryKey: ['list', slug] });
      queryClient.invalidateQueries({ queryKey: ['lists'] });
      setShowEditModal(false);
      setEditError('');
      // If slug changed, navigate to new URL
      if (updatedList.slug !== slug) {
        navigate(`/lists/${updatedList.slug}`, { replace: true });
      }
    },
    onError: (err: unknown) => {
      const error = err as { response?: { data?: { detail?: string } } };
      setEditError(error.response?.data?.detail || 'Failed to update list');
    },
  });

  // Delete list mutation
  const deleteListMutation = useMutation({
    mutationFn: async () => {
      await listsApi.delete(slug!);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['lists'] });
      navigate('/lists');
    },
  });

  const handleAddIoc = (e: React.FormEvent) => {
    e.preventDefault();
    if (!newIocValue.trim()) return;

    addIocMutation.mutate({
      value: newIocValue.trim(),
      comment: newIocComment.trim() || undefined,
    });
  };

  const handleRemoveIoc = () => {
    if (iocToRemove) {
      removeIocMutation.mutate(iocToRemove.id);
      setIocToRemove(null);
    }
  };

  const handleDeleteList = () => {
    deleteListMutation.mutate();
  };

  const openEditModal = () => {
    setEditName(list?.name || '');
    setEditDescription(list?.description || '');
    setEditTags(list?.tags?.join(', ') || '');
    setEditListType(list?.list_type || 'mixed');
    setEditError('');
    setShowEditModal(true);
  };

  const handleEditList = (e: React.FormEvent) => {
    e.preventDefault();
    const tags = editTags
      .split(',')
      .map((t) => t.trim())
      .filter((t) => t.length > 0);

    updateListMutation.mutate({
      name: editName,
      description: editDescription || undefined,
      list_type: editListType || undefined,
      tags: tags.length > 0 ? tags : undefined,
    });
  };

  const getEdlUrl = () => {
    const baseUrl = config?.edl_base_url || window.location.origin;
    return `${baseUrl}/edl/${slug}`;
  };

  const copyEdlUrl = async () => {
    try {
      await navigator.clipboard.writeText(getEdlUrl());
      setCopiedUrl(true);
      setTimeout(() => setCopiedUrl(false), 2000);
    } catch {
      // Fallback for older browsers
      const input = document.createElement('input');
      input.value = getEdlUrl();
      document.body.appendChild(input);
      input.select();
      document.execCommand('copy');
      document.body.removeChild(input);
      setCopiedUrl(true);
      setTimeout(() => setCopiedUrl(false), 2000);
    }
  };

  if (listError) {
    return (
      <div className="list-detail-page">
        <div className="alert alert-error">
          [ERROR] List not found or access denied.
        </div>
        <button className="btn btn-secondary mt-md" onClick={() => navigate('/lists')}>
          &lt; BACK TO LISTS
        </button>
      </div>
    );
  }

  if (listLoading) {
    return (
      <div className="list-detail-page">
        <div className="loading-container">
          <div className="loading-spinner"></div>
          <span className="text-muted">Loading list...</span>
        </div>
      </div>
    );
  }

  return (
    <div className="list-detail-page">
      {/* Header */}
      <header className="page-header">
        <button className="back-link" onClick={() => navigate('/lists')}>
          &lt; Back to Lists
        </button>
        <div className="flex justify-between items-start mt-md">
          <div>
            <h1 className="page-title">{list?.name}</h1>
            {list?.description && (
              <p className="page-subtitle">{list.description}</p>
            )}
          </div>
          <div className="flex gap-sm">
            <button
              className="btn btn-secondary"
              onClick={openEditModal}
            >
              EDIT
            </button>
            <button
              className="btn btn-danger"
              onClick={() => setShowDeleteConfirm(true)}
            >
              DELETE
            </button>
          </div>
        </div>
      </header>

      {/* List Info Panel */}
      <div className="info-panel">
        <div className="info-grid">
          <div className="info-item">
            <span className="info-label">SLUG</span>
            <span className="info-value text-cyan font-mono">{list?.slug}</span>
          </div>
          <div className="info-item">
            <span className="info-label">TYPE</span>
            <span className="info-value">
              <span className="ioc-type">{(list?.list_type || 'mixed').toUpperCase()}</span>
            </span>
          </div>
          <div className="info-item">
            <span className="info-label">IOC COUNT</span>
            <span className="info-value">{list?.ioc_count || 0}</span>
          </div>
          <div className="info-item">
            <span className="info-label">CREATED</span>
            <span className="info-value text-sm">
              {list?.created_at ? new Date(list.created_at).toLocaleString() : '-'}
            </span>
          </div>
          <div className="info-item">
            <span className="info-label">TAGS</span>
            <div className="info-value flex gap-xs flex-wrap">
              {list?.tags && list.tags.length > 0 ? (
                list.tags.map((tag) => (
                  <span key={tag} className="tag">{tag}</span>
                ))
              ) : (
                <span className="text-muted">No tags</span>
              )}
            </div>
          </div>
        </div>

        {/* EDL URL */}
        <div className="edl-url-section">
          <span className="info-label">EDL ENDPOINT URL</span>
          <div className="edl-url-row">
            <code className="edl-url">{getEdlUrl()}</code>
            <button
              className={`btn btn-secondary btn-sm ${copiedUrl ? 'copied' : ''}`}
              onClick={copyEdlUrl}
            >
              {copiedUrl ? 'COPIED!' : 'COPY URL'}
            </button>
          </div>
          <span className="form-hint">
            Use this URL in your firewall EDL configuration. Basic auth required.
          </span>
        </div>
      </div>

      {/* Add IOC Form */}
      <div className="add-ioc-section">
        <h3 className="section-title">Add IOC</h3>
        <form className="add-ioc-form" onSubmit={handleAddIoc}>
          {addError && (
            <div className="alert alert-error mb-md">
              [ERROR] {addError}
            </div>
          )}
          <div className="form-row">
            <div className="form-group flex-grow">
              <label htmlFor="ioc-value">IOC Value *</label>
              <input
                id="ioc-value"
                type="text"
                value={newIocValue}
                onChange={(e) => setNewIocValue(e.target.value)}
                placeholder="IP address, CIDR, or domain"
                required
              />
            </div>
            <div className="form-group flex-grow">
              <label htmlFor="ioc-comment">Comment</label>
              <input
                id="ioc-comment"
                type="text"
                value={newIocComment}
                onChange={(e) => setNewIocComment(e.target.value)}
                placeholder="Optional note"
              />
            </div>
            <button
              type="submit"
              className="btn btn-primary add-btn"
              disabled={addIocMutation.isPending || !newIocValue.trim()}
            >
              {addIocMutation.isPending ? '...' : '+ ADD'}
            </button>
          </div>
        </form>
      </div>

      {/* IOCs Table */}
      <div className="iocs-section">
        <h3 className="section-title">IOCs in List ({iocs?.length || 0})</h3>
        <div className="panel">
          {iocsLoading ? (
            <div className="loading-container">
              <div className="loading-spinner"></div>
            </div>
          ) : iocs && iocs.length > 0 ? (
            <table className="data-table">
              <thead>
                <tr>
                  <th>Value</th>
                  <th>Type</th>
                  <th>Comment</th>
                  <th>Added</th>
                  <th>Actions</th>
                </tr>
              </thead>
              <tbody>
                {iocs.map((ioc) => (
                  <tr key={ioc.id}>
                    <td>
                      <code className="ioc-value">{ioc.value}</code>
                    </td>
                    <td>
                      <span className="ioc-type">{ioc.ioc_type}</span>
                    </td>
                    <td>
                      <span className="text-muted truncate" style={{ maxWidth: '200px', display: 'block' }}>
                        {ioc.comment || '-'}
                      </span>
                    </td>
                    <td>
                      <span className="text-muted text-sm">
                        {new Date(ioc.created_at).toLocaleDateString()}
                      </span>
                    </td>
                    <td>
                      <button
                        className="btn btn-danger btn-sm"
                        onClick={() => setIocToRemove(ioc)}
                        disabled={removeIocMutation.isPending}
                      >
                        REMOVE
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          ) : (
            <div className="empty-state">
              <div className="empty-state-icon">#</div>
              <p className="empty-state-title">No IOCs in this list</p>
              <p className="empty-state-description">
                Add indicators above to populate this EDL
              </p>
            </div>
          )}
        </div>
      </div>

      {/* Delete Confirmation Modal */}
      {showDeleteConfirm && (
        <div className="modal-overlay" onClick={() => setShowDeleteConfirm(false)}>
          <div className="modal-content" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <h3 className="modal-title text-red">Confirm Deletion</h3>
              <button className="modal-close" onClick={() => setShowDeleteConfirm(false)}>
                &times;
              </button>
            </div>

            <div className="delete-warning">
              <p>
                Are you sure you want to delete the list <strong>"{list?.name}"</strong>?
              </p>
              <p className="text-muted mt-sm">
                This will remove the list and all its IOC associations. This action cannot be undone.
              </p>
            </div>

            <div className="flex gap-md justify-end mt-lg">
              <button
                className="btn btn-secondary"
                onClick={() => setShowDeleteConfirm(false)}
              >
                CANCEL
              </button>
              <button
                className="btn btn-danger"
                onClick={handleDeleteList}
                disabled={deleteListMutation.isPending}
              >
                {deleteListMutation.isPending ? 'DELETING...' : 'DELETE LIST'}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Remove IOC Confirmation */}
      {iocToRemove && (
        <ConfirmModal
          title="Remove IOC"
          message={`Remove "${iocToRemove.value}" from this list? The IOC will still exist in the database and can be added to other lists.`}
          confirmText="REMOVE"
          variant="danger"
          onConfirm={handleRemoveIoc}
          onCancel={() => setIocToRemove(null)}
          isLoading={removeIocMutation.isPending}
        />
      )}

      {/* Edit List Modal */}
      {showEditModal && (
        <div className="modal-overlay" onClick={() => setShowEditModal(false)}>
          <div className="modal-content" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <h3 className="modal-title">Edit List</h3>
              <button className="modal-close" onClick={() => setShowEditModal(false)}>
                &times;
              </button>
            </div>

            <form onSubmit={handleEditList}>
              {editError && (
                <div className="alert alert-error mb-md">
                  [ERROR] {editError}
                </div>
              )}

              <div className="form-group">
                <label htmlFor="edit-name">List Name *</label>
                <input
                  id="edit-name"
                  type="text"
                  value={editName}
                  onChange={(e) => setEditName(e.target.value)}
                  required
                />
                <span className="form-hint">
                  Changing the name will update the slug
                </span>
              </div>

              <div className="form-group">
                <label htmlFor="edit-description">Description</label>
                <textarea
                  id="edit-description"
                  value={editDescription}
                  onChange={(e) => setEditDescription(e.target.value)}
                  rows={3}
                />
              </div>

              <div className="form-group">
                <label htmlFor="edit-list-type">List Type</label>
                <select
                  id="edit-list-type"
                  value={editListType}
                  onChange={(e) => setEditListType(e.target.value)}
                >
                  <option value="mixed">Mixed</option>
                  <option value="ip">IP/CIDR</option>
                  <option value="domain">Domain</option>
                  <option value="hash">Hash</option>
                </select>
                <span className="form-hint">
                  Changing the type may fail if existing IOCs are incompatible
                </span>
              </div>

              <div className="form-group">
                <label htmlFor="edit-tags">Tags</label>
                <input
                  id="edit-tags"
                  type="text"
                  value={editTags}
                  onChange={(e) => setEditTags(e.target.value)}
                  placeholder="Comma-separated tags"
                />
              </div>

              <div className="flex gap-md justify-end">
                <button
                  type="button"
                  className="btn btn-secondary"
                  onClick={() => setShowEditModal(false)}
                >
                  CANCEL
                </button>
                <button
                  type="submit"
                  className="btn btn-primary"
                  disabled={updateListMutation.isPending || !editName}
                >
                  {updateListMutation.isPending ? 'SAVING...' : 'SAVE CHANGES'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
