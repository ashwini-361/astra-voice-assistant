const API_BASE = import.meta.env.VITE_LLM_API_BASE ?? 'http://127.0.0.1:8002';

export const fetchProviders = async () => {
  const response = await fetch(`${API_BASE}/api/v1/chat/providers`);
  if (!response.ok) return [];
  return await response.json();
};

export const fetchModels = async (provider: string) => {
  const response = await fetch(`${API_BASE}/api/v1/chat/models?provider=${provider}`);
  if (!response.ok) return [];
  return await response.json();
};
