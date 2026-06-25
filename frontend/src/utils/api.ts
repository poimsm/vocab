const API_URL = 'http://localhost:8000';

import { EXAMPLES } from "@/utils/dummy"

export { API_URL };

export async function fetchJson<T>(
  url: string,
  options?: RequestInit
): Promise<T> {
  const response = await fetch(url, options);
  if (!response.ok) {
    throw new Error(`HTTP ${response.status}`);
  }
  return response.json();
}

export interface Example {
  id: number;
  text: string;
  is_favorite?: boolean;
}

export interface Favorite {
  id: number;
  example: string;
  created_at: string;
}

export interface Word {
  id: number;
  main: string;
  is_learned: boolean;
}

export interface Session {
  id: number;
  created_at: string;
  examples: Example[];
}

export interface ToggleWordLearnedResponse {
  id: number;
  is_learned: boolean;
  message: string;
}

export async function getExamples(): Promise<Example[]> {
  return EXAMPLES;
  return fetchJson<Example[]>(`${API_URL}/examples/daily`);
}

export async function getFavorites(): Promise<Favorite[]> {
  // await new Promise(r => setTimeout(r, 1000));
  return fetchJson<Favorite[]>(`${API_URL}/favorites`);
}

export async function getSessions(): Promise<Session[]> {
  return fetchJson<Session[]>(`${API_URL}/sessions`);
}

export async function getWords(): Promise<Word[]> {
  return fetchJson<Word[]>(`${API_URL}/words/daily`);
}

export async function addFavorite(exampleId: number): Promise<void> {
  await fetchJson<void>(`${API_URL}/favorites/${exampleId}`, {
    method: 'POST'
  });
}

export async function removeFavorite(exampleId: number): Promise<void> {
  await fetchJson<void>(`${API_URL}/favorites/${exampleId}`, {
    method: 'DELETE'
  });
}

export async function saveWord(text: string): Promise<void> {
  await fetchJson<void>(`${API_URL}/words`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ text })
  });
}

export async function toggleWordLearned(wordId: number): Promise<ToggleWordLearnedResponse> {
  return fetchJson<ToggleWordLearnedResponse>(`${API_URL}/words/${wordId}/toggle-learned`, {
    method: "PATCH",
  });
}
