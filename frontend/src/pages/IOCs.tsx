import { useState, useEffect } from 'react';
import { useQuery } from '@tanstack/react-query';
import { useNavigate } from 'react-router-dom';
import { iocsApi } from '../api/client';
import './IOCs.css';

export default function IOCs() {
  const navigate = useNavigate();
  const [searchInput, setSearchInput] = useState('');
  const [debouncedQuery, setDebouncedQuery] = useState('');

  // Debounce search
  useEffect(() => {
    const timer = setTimeout(() => {
      setDebouncedQuery(searchInput);
    }, 300);
    return () => clearTimeout(timer);
  }, [searchInput]);

  const { data: iocs, isLoading } = useQuery({
    queryKey: ['iocs', debouncedQuery],
    queryFn: async () => {
      const response = await iocsApi.list(debouncedQuery || undefined);
      return response.data;
    },
  });

  const filteredIocs = iocs || [];

  return (
    <div className="iocs-page">
      <header className="page-header">
        <h1 className="page-title">IOCs</h1>
        <p className="page-subtitle">Manage indicators across all lists</p>
      </header>

      {/* Stats Callout */}
      <div className="iocs-stats-callout">
        <span className="status-dot active"></span>
        <span>
          {isLoading ? 'Loading...' : `${filteredIocs.length} indicator${filteredIocs.length !== 1 ? 's' : ''} tracked`}
        </span>
      </div>

      {/* Search Form */}
      <div className="search-form-container">
        <div className="search-input-wrapper">
          <span className="search-prompt">$&gt;</span>
          <input
            type="text"
            className="search-input"
            placeholder="Search IOCs by value..."
            value={searchInput}
            onChange={(e) => setSearchInput(e.target.value)}
          />
          {isLoading && <span className="loading-spinner"></span>}
        </div>
      </div>

      {/* IOCs Table */}
      <div className="panel">
        {isLoading ? (
          <div className="loading-container">
            <div className="loading-spinner"></div>
          </div>
        ) : filteredIocs.length > 0 ? (
          <table className="data-table">
            <thead>
              <tr>
                <th>Value</th>
                <th>Type</th>
                <th>Lists</th>
                <th>Added</th>
              </tr>
            </thead>
            <tbody>
              {filteredIocs.map((ioc) => (
                <tr
                  key={ioc.id}
                  className="clickable"
                  onClick={() => navigate(`/iocs/${ioc.id}`)}
                >
                  <td>
                    <code className="ioc-value">{ioc.value}</code>
                  </td>
                  <td>
                    <span className="ioc-type-badge">{ioc.ioc_type}</span>
                  </td>
                  <td>
                    <span className="list-count">
                      {ioc.lists.length === 0
                        ? 'No lists'
                        : ioc.lists.length === 1
                        ? ioc.lists[0].name
                        : `${ioc.lists.length} lists`}
                    </span>
                  </td>
                  <td className="text-muted text-sm">
                    {new Date(ioc.created_at).toLocaleDateString()}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        ) : (
          <div className="empty-state">
            <div className="empty-state-icon">#</div>
            <p className="empty-state-title">
              {searchInput ? 'No IOCs match your search' : 'No IOCs yet'}
            </p>
            <p className="empty-state-description">
              {searchInput
                ? 'Try a different search term'
                : 'Add IOCs through lists or the API'}
            </p>
          </div>
        )}
      </div>
    </div>
  );
}
