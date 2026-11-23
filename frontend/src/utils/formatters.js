/**
 * Formatting utilities for DealerOS.
 * Adheres strictly to Indian Rupee (INR) monetary formatting,
 * 2-decimal precision, and explicit null-handling rules.
 */

const INR_FORMATTER = new Intl.NumberFormat('en-IN', {
  style: 'currency',
  currency: 'INR',
  minimumFractionDigits: 2,
  maximumFractionDigits: 2,
});

/**
 * Format monetary values as INR.
 * Returns an em dash ('—') for null/undefined values. Never returns ₹0 for null.
 */
export function formatCurrencyINR(value) {
  if (value === null || value === undefined || value === '') {
    return '—';
  }
  const numeric = typeof value === 'number' ? value : parseFloat(value);
  if (Number.isNaN(numeric)) {
    return '—';
  }
  return INR_FORMATTER.format(numeric);
}

/**
 * Format variance/difference as INR with explicit +/- signs.
 * Returns em dash ('—') for null values.
 */
export function formatDifferenceINR(value) {
  if (value === null || value === undefined || value === '') {
    return '—';
  }
  const numeric = typeof value === 'number' ? value : parseFloat(value);
  if (Number.isNaN(numeric)) {
    return '—';
  }
  if (numeric > 0) {
    return `+${INR_FORMATTER.format(numeric)}`;
  }
  return INR_FORMATTER.format(numeric);
}

/**
 * Format monetary values for the Details Drawer.
 * Returns 'Unavailable' when null, ensuring users know data was missing/blank.
 */
export function formatDetailsCurrency(value) {
  if (value === null || value === undefined || value === '') {
    return 'Unavailable';
  }
  const numeric = typeof value === 'number' ? value : parseFloat(value);
  if (Number.isNaN(numeric)) {
    return 'Unavailable';
  }
  return INR_FORMATTER.format(numeric);
}

/**
 * Format location strings.
 * Respects cross-tenant data redaction by rendering 'Restricted'.
 */
export function formatLocation(location, { isRedacted = false } = {}) {
  if (isRedacted || (location === null && isRedacted)) {
    return 'Restricted';
  }
  if (!location || location === 'null') {
    return '—';
  }
  return location;
}

/**
 * Format ISO dates (YYYY-MM-DD) into clean readable format.
 */
export function formatDate(dateStr) {
  if (!dateStr || dateStr === 'null') {
    return '—';
  }
  try {
    const [year, month, day] = dateStr.split('-');
    if (year && month && day) {
      const date = new Date(year, month - 1, day);
      return date.toLocaleDateString('en-US', {
        month: 'short',
        day: 'numeric',
        year: 'numeric',
      });
    }
    return dateStr;
  } catch {
    return dateStr;
  }
}
