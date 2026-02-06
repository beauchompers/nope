import { useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { iocsApi, listsApi, type IOCDetail as IOCDetailType } from '../api/client';
import ConfirmModal from '../components/ConfirmModal';
import './IOCDetail.css';

/**
 * Checks if an IOC type is compatible with a list type.
 * @param listType - The list's type (mixed, ip, domain, hash)
 * @param iocType - The IOC's type (ip, domain, wildcard, md5, sha1, sha256)
 * @returns true if the IOC type is allowed for the list type
 */
function isIOCTypeCompatibleWithList(listType: string, iocType: string): boolean {
  switch (listType) {
    case 'mixed':
      return true;
    case 'ip':
      return iocType === 'ip';
    case 'domain':
      return iocType === 'domain' || iocType === 'wildcard';
    case 'hash':
      return iocType === 'md5' || iocType === 'sha1' || iocType === 'sha256';
    default:
      return true; // Unknown list types accept all IOC types
  }
}

export default function IOCDetail() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const iocId = parseInt(id!, 10);

  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);
  const [selectedList, setSelectedList] = useState('');
  const [newComment, setNewComment] = useState('');
  const [listToRemove, setListToRemove] = useState<{ slug: string; name: string } | null>(null);

  // Fetch IOC details
  const { data: ioc, isLoading, error } = useQuery({
    queryKey: ['ioc', iocId],
    queryFn: async () => {
      const response = await iocsApi.get(iocId);
      return response.data as IOCDetailType;
    },
  });

  // Fetch all lists for "Add to List" dropdown
  const { data: allLists } = useQuery({
    queryKey: ['lists'],
    queryFn: async () => {
      const response = await listsApi.getAll();
      return response.data;
    },
  });

  // Lists the IOC is NOT on and that are compatible with the IOC type
  const availableLists = allLists?.filter(
    (list) => !ioc?.lists.some((l) => l.slug === list.slug) &&
      isIOCTypeCompatibleWithList(list.list_type || 'mixed', ioc?.ioc_type || '')
  ) || [];

  // Delete IOC mutation
  const deleteMutation = useMutation({
    mutationFn: () => iocsApi.delete(iocId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['iocs'] });
      navigate('/iocs');
    },
  });

  // Remove from list mutation
  const removeFromListMutation = useMutation({
    mutationFn: (slug: string) => iocsApi.removeFromList(iocId, slug),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['ioc', iocId] });
      queryClient.invalidateQueries({ queryKey: ['lists'] });
      setListToRemove(null);
    },
  });

  // Add to list mutation
  const addToListMutation = useMutation({
    mutationFn: (slug: string) => iocsApi.addToList(iocId, slug),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['ioc', iocId] });
      queryClient.invalidateQueries({ queryKey: ['lists'] });
      setSelectedList('');
    },
  });

  // Add comment mutation
  const addCommentMutation = useMutation({
    mutationFn: (content: string) => iocsApi.addComment(iocId, content),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['ioc', iocId] });
      setNewComment('');
    },
  });

  const handleAddToList = () => {
    if (selectedList) {
      addToListMutation.mutate(selectedList);
    }
  };

  const handleAddComment = (e: React.FormEvent) => {
    e.preventDefault();
    if (newComment.trim()) {
      addCommentMutation.mutate(newComment.trim());
    }
  };

  const handleRemoveFromList = () => {
    if (listToRemove) {
      removeFromListMutation.mutate(listToRemove.slug);
    }
  };

  const formatTimeAgo = (dateStr: string) => {
    const date = new Date(dateStr);
    const now = new Date();
    const diffMs = now.getTime() - date.getTime();
    const diffMins = Math.floor(diffMs / 60000);
    const diffHours = Math.floor(diffMins / 60);
    const diffDays = Math.floor(diffHours / 24);

    if (diffDays > 0) return `${diffDays} day${diffDays > 1 ? 's' : ''} ago`;
    if (diffHours > 0) return `${diffHours} hour${diffHours > 1 ? 's' : ''} ago`;
    if (diffMins > 0) return `${diffMins} min${diffMins > 1 ? 's' : ''} ago`;
    return 'Just now';
  };

  const getActivityIcon = (action: string) => {
    switch (action) {
      case 'created': return '+';
      case 'added_to_list': return '>';
      case 'removed_from_list': return '<';
      case 'comment': return '#';
      default: return '•';
    }
  };

  const getActivityDescription = (entry: IOCDetailType['audit_history'][0]) => {
    switch (entry.action) {
      case 'created':
        return `Created by ${entry.performed_by || 'system'}`;
      case 'added_to_list':
        return `Added to ${entry.list_name || entry.list_slug} by ${entry.performed_by || 'system'}`;
      case 'removed_from_list':
        return `Removed from ${entry.list_name || entry.list_slug || 'a list'} by ${entry.performed_by || 'system'}`;
      case 'comment':
        return `Comment by ${entry.performed_by || 'system'}`;
      default:
        return entry.action;
    }
  };

  if (error) {
    return (
      <div className="ioc-detail-page">
        <div className="alert alert-error">
          [ERROR] IOC not found or access denied.
        </div>
        <button className="btn btn-secondary mt-md" onClick={() => navigate('/iocs')}>
          &lt; BACK TO IOCS
        </button>
      </div>
    );
  }

  if (isLoading || !ioc) {
    return (
      <div className="ioc-detail-page">
        <div className="loading-container">
          <div className="loading-spinner"></div>
          <span className="text-muted">Loading IOC...</span>
        </div>
      </div>
    );
  }

  return (
    <div className="ioc-detail-page">
      {/* Header */}
      <header className="page-header">
        <button className="back-link" onClick={() => navigate('/iocs')}>
          &lt; Back to IOCs
        </button>
        <div className="flex justify-between items-start mt-md">
          <div>
            <h1 className="page-title ioc-value-title">{ioc.value}</h1>
            <p className="page-subtitle">Indicator of Compromise</p>
          </div>
          <button
            className="btn btn-danger"
            onClick={() => setShowDeleteConfirm(true)}
          >
            DELETE
          </button>
        </div>
      </header>

      {/* IOC Info Panel */}
      <div className="info-panel">
        <div className="info-grid">
          <div className="info-item">
            <span className="info-label">TYPE</span>
            <span className="info-value">
              <span className="ioc-type-badge">{ioc.ioc_type}</span>
            </span>
          </div>
          <div className="info-item">
            <span className="info-label">LIST MEMBERSHIPS</span>
            <span className="info-value">{ioc.lists.length}</span>
          </div>
          <div className="info-item">
            <span className="info-label">CREATED</span>
            <span className="info-value text-sm">
              {new Date(ioc.created_at).toLocaleString()}
            </span>
          </div>
          <div className="info-item">
            <span className="info-label">LAST UPDATED</span>
            <span className="info-value text-sm">
              {new Date(ioc.updated_at).toLocaleString()}
            </span>
          </div>
        </div>
      </div>

      {/* List Memberships Section */}
      <section className="lists-section">
        <h3 className="section-title">List Memberships ({ioc.lists.length})</h3>
        <div className="panel">
          {ioc.lists.length > 0 ? (
            <table className="data-table">
              <thead>
                <tr>
                  <th>List Name</th>
                  <th>Actions</th>
                </tr>
              </thead>
              <tbody>
                {ioc.lists.map((list) => (
                  <tr key={list.slug} className="clickable" onClick={() => navigate(`/lists/${list.slug}`)}>
                    <td>
                      <span className="text-cyan font-mono">{list.name}</span>
                    </td>
                    <td>
                      <button
                        className="btn btn-danger btn-sm"
                        onClick={(e) => {
                          e.stopPropagation();
                          setListToRemove(list);
                        }}
                        disabled={removeFromListMutation.isPending}
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
              <div className="empty-state-icon">[_]</div>
              <p className="empty-state-title">Not on any lists</p>
              <p className="empty-state-description">
                Add this IOC to a list below
              </p>
            </div>
          )}

          {/* Add to List */}
          {availableLists.length > 0 && (
            <div className="add-to-list-section">
              <div className="add-to-list-row">
                <select
                  value={selectedList}
                  onChange={(e) => setSelectedList(e.target.value)}
                  className="add-to-list-select"
                >
                  <option value="">Select a list to add to...</option>
                  {availableLists.map((list) => (
                    <option key={list.slug} value={list.slug}>
                      {list.name}
                    </option>
                  ))}
                </select>
                <button
                  className="btn btn-primary"
                  onClick={handleAddToList}
                  disabled={!selectedList || addToListMutation.isPending}
                >
                  {addToListMutation.isPending ? '...' : '+ ADD'}
                </button>
              </div>
            </div>
          )}
        </div>
      </section>

      {/* Activity History Section */}
      <section className="activity-section">
        <h3 className="section-title">Activity History ({ioc.audit_history.length})</h3>

        {/* Add Comment Form */}
        <form className="add-comment-form" onSubmit={handleAddComment}>
          <div className="form-row">
            <div className="form-group flex-grow">
              <input
                type="text"
                placeholder="Add a comment..."
                value={newComment}
                onChange={(e) => setNewComment(e.target.value)}
              />
            </div>
            <button
              type="submit"
              className="btn btn-primary add-btn"
              disabled={!newComment.trim() || addCommentMutation.isPending}
            >
              {addCommentMutation.isPending ? '...' : '+ ADD'}
            </button>
          </div>
        </form>

        {/* Activity Timeline */}
        <div className="panel activity-panel">
          {ioc.audit_history.length > 0 ? (
            <div className="activity-timeline">
              {ioc.audit_history.map((entry) => (
                <div key={entry.id} className="activity-entry">
                  <div className="activity-icon">{getActivityIcon(entry.action)}</div>
                  <div className="activity-content">
                    <div className="activity-description">
                      {getActivityDescription(entry)}
                    </div>
                    {entry.action === 'comment' && entry.content && (
                      <div className="activity-comment">{entry.content}</div>
                    )}
                  </div>
                  <div className="activity-time">{formatTimeAgo(entry.created_at)}</div>
                </div>
              ))}
            </div>
          ) : (
            <div className="empty-state">
              <div className="empty-state-icon">&gt;_</div>
              <p className="empty-state-title">No activity recorded</p>
            </div>
          )}
        </div>
      </section>

      {/* Delete Confirmation */}
      {showDeleteConfirm && (
        <ConfirmModal
          title="Delete IOC"
          message={`Permanently delete "${ioc.value}"? This will remove it from all lists and cannot be undone.`}
          confirmText="DELETE"
          variant="danger"
          onConfirm={() => deleteMutation.mutate()}
          onCancel={() => setShowDeleteConfirm(false)}
          isLoading={deleteMutation.isPending}
        />
      )}

      {/* Remove from List Confirmation */}
      {listToRemove && (
        <ConfirmModal
          title="Remove from List"
          message={`Remove this IOC from "${listToRemove.name}"? The IOC will still exist in the database.`}
          confirmText="REMOVE"
          variant="danger"
          onConfirm={handleRemoveFromList}
          onCancel={() => setListToRemove(null)}
          isLoading={removeFromListMutation.isPending}
        />
      )}
    </div>
  );
}
