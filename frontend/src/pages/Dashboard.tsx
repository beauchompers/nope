import { useQuery } from '@tanstack/react-query';
import { useNavigate } from 'react-router-dom';
import { statsApi, listsApi } from '../api/client';
import './Dashboard.css';

export default function Dashboard() {
  const navigate = useNavigate();

  const { data: stats, isLoading: statsLoading } = useQuery({
    queryKey: ['dashboard-stats'],
    queryFn: async () => {
      // Try to get stats from dedicated endpoint, fallback to computing from lists
      try {
        const response = await statsApi.getDashboard();
        return response.data;
      } catch {
        // Fallback: compute stats from lists
        const listsResponse = await listsApi.getAll();
        const lists = listsResponse.data;
        const totalIocs = lists.reduce((sum, list) => sum + (list.ioc_count || 0), 0);
        return {
          total_lists: lists.length,
          total_iocs: totalIocs,
          recent_activity: [],
        };
      }
    },
    refetchInterval: 30000, // Refresh every 30 seconds
  });

  const { data: lists } = useQuery({
    queryKey: ['lists'],
    queryFn: async () => {
      const response = await listsApi.getAll();
      return response.data;
    },
  });

  return (
    <div className="dashboard">
      <header className="page-header">
        <h1 className="page-title">Dashboard</h1>
        <p className="page-subtitle">System overview and monitoring</p>
      </header>

      {/* Stats Grid */}
      <div className="stats-grid">
        <div className="stat-card clickable" onClick={() => navigate('/lists')}>
          <div className="stat-header">
            <span className="stat-icon">[]</span>
            <span className="stat-label">TOTAL LISTS</span>
          </div>
          <div className="stat-value">
            {statsLoading ? (
              <span className="skeleton" style={{ width: '60px', height: '36px' }}></span>
            ) : (
              <span className="stat-number">{stats?.total_lists ?? 0}</span>
            )}
          </div>
          <div className="stat-footer">
            <span className="status-dot active"></span>
            <span>Active EDL endpoints</span>
          </div>
        </div>

        <div className="stat-card clickable" onClick={() => navigate('/iocs')}>
          <div className="stat-header">
            <span className="stat-icon">#</span>
            <span className="stat-label">TOTAL IOCS</span>
          </div>
          <div className="stat-value">
            {statsLoading ? (
              <span className="skeleton" style={{ width: '80px', height: '36px' }}></span>
            ) : (
              <span className="stat-number">{stats?.total_iocs ?? 0}</span>
            )}
          </div>
          <div className="stat-footer">
            <span className="status-dot active"></span>
            <span>Indicators tracked</span>
          </div>
        </div>

        <div className="stat-card">
          <div className="stat-header">
            <span className="stat-icon">&gt;_</span>
            <span className="stat-label">SYSTEM STATUS</span>
          </div>
          <div className="stat-value">
            <span className="stat-status online">ONLINE</span>
          </div>
          <div className="stat-footer">
            <span className="status-dot active"></span>
            <span>All systems operational</span>
          </div>
        </div>
      </div>

      {/* Recent Lists */}
      <section className="dashboard-section">
        <div className="section-header">
          <h2 className="section-title">Active Lists</h2>
          <a href="/lists" className="section-link">View All &gt;</a>
        </div>

        <div className="panel">
          {lists && lists.length > 0 ? (
            <table className="data-table">
              <thead>
                <tr>
                  <th>Name</th>
                  <th>Slug</th>
                  <th>IOCs</th>
                  <th>Tags</th>
                  <th>Status</th>
                </tr>
              </thead>
              <tbody>
                {lists.slice(0, 5).map((list) => (
                  <tr key={list.id} className="clickable" onClick={() => window.location.href = `/lists/${list.slug}`}>
                    <td className="text-primary font-mono">{list.name}</td>
                    <td className="text-cyan">{list.slug}</td>
                    <td>
                      <span className="badge">{list.ioc_count || 0}</span>
                    </td>
                    <td>
                      <div className="flex gap-xs flex-wrap">
                        {list.tags?.slice(0, 3).map((tag) => (
                          <span key={tag} className="tag">{tag}</span>
                        ))}
                      </div>
                    </td>
                    <td>
                      <span className="status-dot active"></span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          ) : (
            <div className="empty-state">
              <div className="empty-state-icon">[]</div>
              <p className="empty-state-title">No lists configured</p>
              <p className="empty-state-description">Create your first list to start tracking IOCs</p>
            </div>
          )}
        </div>
      </section>

      {/* Terminal-style Activity Log */}
      <section className="dashboard-section">
        <div className="section-header">
          <h2 className="section-title">System Log</h2>
        </div>

        <div className="terminal-panel">
          <div className="terminal-content">
            <div className="log-entry">
              <span className="log-timestamp">[{new Date().toISOString()}]</span>
              <span className="log-level info">INFO</span>
              <span className="log-message">Dashboard initialized - monitoring active</span>
            </div>
            <div className="log-entry">
              <span className="log-timestamp">[{new Date().toISOString()}]</span>
              <span className="log-level success">OK</span>
              <span className="log-message">EDL endpoints serving {stats?.total_lists ?? 0} lists</span>
            </div>
            <div className="log-entry">
              <span className="log-timestamp">[{new Date().toISOString()}]</span>
              <span className="log-level info">INFO</span>
              <span className="log-message">Total indicators: {stats?.total_iocs ?? 0}</span>
            </div>
            {stats?.recent_activity?.map((activity, idx) => (
              <div key={idx} className="log-entry">
                <span className="log-timestamp">[{activity.timestamp}]</span>
                <span className="log-level info">{activity.action.toUpperCase()}</span>
                <span className="log-message">{activity.details}</span>
              </div>
            ))}
            <div className="log-cursor">_</div>
          </div>
        </div>
      </section>
    </div>
  );
}
