import axios from 'axios';

const api = axios.create({
  baseURL: '/api',
});

api.interceptors.request.use((config) => {
  const token = localStorage.getItem('token');
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      localStorage.removeItem('token');
      window.location.href = '/login';
    }
    return Promise.reject(error);
  }
);

export default api;

// Types
export interface List {
  id: number;
  name: string;
  slug: string;
  description?: string;
  list_type: string;
  tags: string[];
  ioc_count: number;
  created_at: string;
  updated_at: string;
}

export interface IOC {
  id: number;
  value: string;
  ioc_type: string;
  comment?: string;
  lists: { slug: string; name: string }[];
  created_at: string;
}

export interface IOCDetail extends IOC {
  updated_at: string;
  audit_history: {
    id: number;
    action: string;
    list_slug?: string;
    list_name?: string;
    content?: string;
    performed_by?: string;
    created_at: string;
  }[];
}

export interface Activity {
  id: number;
  action: string;
  details: string;
  timestamp: string;
}

// API functions
export const listsApi = {
  getAll: () => api.get<List[]>('/lists'),
  get: (slug: string) => api.get<List>(`/lists/${slug}`),
  create: (data: { name: string; description?: string; list_type?: string; tags?: string[] }) =>
    api.post<List>('/lists', data),
  update: (slug: string, data: { name?: string; description?: string; list_type?: string; tags?: string[] }) =>
    api.patch<List>(`/lists/${slug}`, data),
  delete: (slug: string) => api.delete(`/lists/${slug}`),
  getIOCs: (slug: string) => api.get<IOC[]>(`/lists/${slug}/iocs`),
};

export const iocsApi = {
  list: (query?: string) =>
    api.get<IOC[]>(query ? `/iocs?q=${encodeURIComponent(query)}` : '/iocs'),
  search: (query: string) => api.get<IOC[]>(`/iocs?q=${encodeURIComponent(query)}`),
  get: (id: number) => api.get<IOCDetail>(`/iocs/${id}`),
  create: (data: { value: string; list_slugs?: string[]; comment?: string }) =>
    api.post<IOC>('/iocs', data),
  delete: (id: number) => api.delete(`/iocs/${id}`),
  removeFromList: (id: number, slug: string) => api.delete(`/iocs/${id}/lists/${slug}`),
  addToList: (id: number, slug: string) => api.post(`/iocs/${id}/lists/${slug}`),
  addComment: (id: number, content: string) => api.post(`/iocs/${id}/comments`, { content }),
};

export const authApi = {
  login: (username: string, password: string) => {
    const formData = new FormData();
    formData.append('username', username);
    formData.append('password', password);
    return api.post<{ access_token: string; token_type: string }>('/auth/login', formData);
  },
  me: () => api.get<{ username: string }>('/auth/me'),
};

export const statsApi = {
  getDashboard: () => api.get<{
    total_lists: number;
    total_iocs: number;
    recent_activity: Activity[];
  }>('/stats/dashboard'),
};

export interface PublicConfig {
  edl_base_url: string;
}

export interface EdlUrlConfig {
  host: string;
  port: number;
  full_url: string;
}

export interface EdlUrlUpdate {
  host: string;
  port: number;
}

export interface Credential {
  id: number;
  username: string;
}

export interface User {
  id: number;
  username: string;
}

export interface Exclusion {
  id: number;
  value: string;
  type: string;
  reason?: string;
  is_builtin: boolean;
}

export interface APIKey {
  id: number;
  name: string;
  key: string;
  created_at: string;
  last_used_at: string | null;
}

export const settingsApi = {
  getConfig: () => api.get<PublicConfig>('/settings/config'),
  // EDL URL Configuration
  getEdlUrl: () => api.get<EdlUrlConfig>('/settings/edl-url'),
  updateEdlUrl: (data: EdlUrlUpdate) => api.put<EdlUrlConfig>('/settings/edl-url', data),
  // Users
  getUsers: () => api.get<User[]>('/settings/users'),
  createUser: (data: { username: string; password: string }) =>
    api.post<User>('/settings/users', data),
  deleteUser: (id: number) => api.delete(`/settings/users/${id}`),
  // EDL Credential (single global credential)
  getCredential: () => api.get<Credential>('/settings/credential'),
  updateCredential: (data: { username: string; password?: string }) =>
    api.put<Credential>('/settings/credential', data),
  // Exclusions
  getExclusions: () => api.get<Exclusion[]>('/settings/exclusions'),
  createExclusion: (data: { value: string; type: string; reason?: string }) =>
    api.post<Exclusion>('/settings/exclusions', data),
  deleteExclusion: (id: number) => api.delete(`/settings/exclusions/${id}`),
  // API Keys
  getApiKeys: () => api.get<APIKey[]>('/settings/api-keys'),
  createApiKey: (name: string) => api.post<APIKey>('/settings/api-keys', { name }),
  deleteApiKey: (id: number) => api.delete(`/settings/api-keys/${id}`),
};
