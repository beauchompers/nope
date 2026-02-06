import { useState, useEffect } from 'react';
import { useQuery } from '@tanstack/react-query';
import { useNavigate } from 'react-router-dom';
import { iocsApi } from '../api/client';
import type { IOC } from '../api/client';
import './Search.css';

export default function Search() {
  const [searchInput, setSearchInput] = useState('');
  const [debouncedQuery, setDebouncedQuery] = useState('');
  const navigate = useNavigate();

  // Debounce search
  useEffect(() => {
    const timer = setTimeout(() => {
      setDebouncedQuery(searchInput);
    }, 300);
    return () => clearTimeout(timer);
  }, [searchInput]);

  const { data: results, isLoading, error } = useQuery({
    queryKey: ['ioc-search', debouncedQuery],
    queryFn: async () => {
      if (!debouncedQuery) return [];
      const response = await iocsApi.search(debouncedQuery);
      return response.data;
    },
    enabled: debouncedQuery.length > 0,
  });

  const handleIocClick = (ioc: IOC) => {
    navigate(`/iocs/${ioc.id}`);
  };

  return (
    <div className="search-page">
      <header className="page-header">
        <h1 className="page-title">Search IOCs</h1>
        <p className="page-subtitle">Find indicators across all lists</p>
      </header>

      {/* Search Form */}
      <div className="search-form-container">
        <div className="search-input-wrapper">
          <span className="search-prompt">$&gt;</span>
          <input
            type="text"
            className="search-input"
            value={searchInput}
            onChange={(e) => setSearchInput(e.target.value)}
            placeholder="Search by IP address, CIDR, or domain..."
            autoFocus
          />
          {isLoading && <span className="loading-spinner"></span>}
        </div>
      </div>

      {/* Results */}
      <div className="search-results">
        {error && (
          <div className="alert alert-error">
            [ERROR] Search failed. Please try again.
          </div>
        )}

        {debouncedQuery && !isLoading && (
          <div className="results-header">
            <span className="results-count">
              {results?.length || 0} result{results?.length !== 1 ? 's' : ''} for "{debouncedQuery}"
            </span>
          </div>
        )}

        {debouncedQuery && !isLoading && results && results.length > 0 && (
          <div className="panel">
            <table className="data-table">
              <thead>
                <tr>
                  <th>IOC Value</th>
                  <th>Type</th>
                  <th>Lists</th>
                  <th>Comment</th>
                  <th>Created</th>
                </tr>
              </thead>
              <tbody>
                {results.map((ioc) => (
                  <tr
                    key={ioc.id}
                    className="clickable"
                    onClick={() => handleIocClick(ioc)}
                  >
                    <td>
                      <code className="ioc-value">{highlightMatch(ioc.value, debouncedQuery)}</code>
                    </td>
                    <td>
                      <span className="ioc-type-badge">{ioc.ioc_type}</span>
                    </td>
                    <td>
                      <div className="lists-cell">
                        {ioc.lists?.length > 0 ? (
                          ioc.lists.map((list) => (
                            <span key={list.slug} className="list-tag">
                              {list.name}
                            </span>
                          ))
                        ) : (
                          <span className="text-muted">No lists</span>
                        )}
                      </div>
                    </td>
                    <td>
                      <span className="comment-preview">
                        {ioc.comment || '-'}
                      </span>
                    </td>
                    <td>
                      <span className="text-muted text-sm">
                        {new Date(ioc.created_at).toLocaleDateString()}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        {debouncedQuery && !isLoading && results && results.length === 0 && (
          <div className="empty-state">
            <div className="empty-state-icon">?/</div>
            <p className="empty-state-title">No matches found</p>
            <p className="empty-state-description">
              No IOCs match your search query. Try a different search term.
            </p>
          </div>
        )}

        {!debouncedQuery && (
          <div className="search-tips">
            <h3 className="tips-title">// Search Tips</h3>
            <ul className="tips-list">
              <li>Search for IP addresses: <code>192.168.1.1</code></li>
              <li>Search for CIDR ranges: <code>10.0.0.0/8</code></li>
              <li>Search for domains: <code>malicious.example.com</code></li>
              <li>Partial matches are supported</li>
            </ul>
          </div>
        )}
      </div>
    </div>
  );
}

// Helper function to highlight search matches
function highlightMatch(value: string, query: string): React.ReactNode {
  if (!query) return value;

  const lowerValue = value.toLowerCase();
  const lowerQuery = query.toLowerCase();
  const index = lowerValue.indexOf(lowerQuery);

  if (index === -1) return value;

  return (
    <>
      {value.substring(0, index)}
      <span className="highlight">{value.substring(index, index + query.length)}</span>
      {value.substring(index + query.length)}
    </>
  );
}
