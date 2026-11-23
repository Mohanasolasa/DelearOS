/**
 * API client service for DealerOS.
 * Connects to Django REST Framework backend with configurable base URL.
 */

const BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000';

export async function fetchDisagreements({ org, reason, sort } = {}) {
  if (!org) {
    throw new Error('Organization identifier is required.');
  }

  const params = new URLSearchParams();
  params.append('org', org);

  if (reason && reason.trim() && reason !== 'ALL') {
    params.append('reason', reason.trim());
  }

  if (sort && sort.trim()) {
    params.append('sort', sort.trim());
  }

  const url = `${BASE_URL}/api/disagreements/?${params.toString()}`;

  const response = await fetch(url, {
    method: 'GET',
    headers: {
      'Accept': 'application/json',
      'Content-Type': 'application/json',
    },
  });

  if (!response.ok) {
    let errorMessage = `API request failed with status ${response.status}`;
    try {
      const errData = await response.json();
      if (errData && errData.error) {
        errorMessage = errData.error;
      }
    } catch {
      // fallback to status message
    }
    throw new Error(errorMessage);
  }

  return response.json();
}
