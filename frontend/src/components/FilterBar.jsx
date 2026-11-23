import React from 'react';
import { Filter, ArrowUpDown, XCircle } from 'lucide-react';

const REASON_OPTIONS = [
  { value: 'ALL', label: 'All Reasons' },
  { value: 'MISSING_IN_B', label: 'Missing in System B' },
  { value: 'ORPHAN_IN_B', label: 'Orphan Entry in System B' },
  { value: 'DUPLICATE_IN_B', label: 'Duplicate in System B' },
  { value: 'VALUE_MISMATCH', label: 'Value Mismatch' },
  { value: 'LOCATION_MISMATCH', label: 'Location Mismatch' },
  { value: 'DATE_MISMATCH', label: 'Date Mismatch' },
  { value: 'VOIDED_IN_B', label: 'Voided Record in System B' },
];

const SORT_OPTIONS = [
  { value: 'record_id', label: 'Record ID (Ascending)' },
  { value: 'value_asc', label: 'Monetary Value (Low to High)' },
  { value: 'value_desc', label: 'Monetary Value (High to Low)' },
  { value: 'difference_asc', label: 'Difference Variance (Low to High)' },
  { value: 'difference_desc', label: 'Difference Variance (High to Low)' },
];

export default function FilterBar({
  selectedReason,
  onSelectReason,
  selectedSort,
  onSelectSort,
  totalResults,
  filteredCount,
  isLoading,
}) {
  const isFiltered = selectedReason && selectedReason !== 'ALL';

  return (
    <div className="filter-bar-container">
      <div className="filter-controls-group">
        {/* Reason Filter */}
        <div className="filter-control">
          <label htmlFor="reason-filter" className="filter-label">
            <Filter size={14} className="filter-icon" />
            <span>Reason:</span>
          </label>
          <select
            id="reason-filter"
            className="filter-select"
            value={selectedReason}
            onChange={(e) => onSelectReason(e.target.value)}
            disabled={isLoading}
          >
            {REASON_OPTIONS.map((opt) => (
              <option key={opt.value} value={opt.value}>
                {opt.label}
              </option>
            ))}
          </select>
        </div>

        {/* Sort Order */}
        <div className="filter-control">
          <label htmlFor="sort-filter" className="filter-label">
            <ArrowUpDown size={14} className="filter-icon" />
            <span>Sort by:</span>
          </label>
          <select
            id="sort-filter"
            className="filter-select"
            value={selectedSort}
            onChange={(e) => onSelectSort(e.target.value)}
            disabled={isLoading}
          >
            {SORT_OPTIONS.map((opt) => (
              <option key={opt.value} value={opt.value}>
                {opt.label}
              </option>
            ))}
          </select>
        </div>

        {/* Clear Filter Shortcut */}
        {isFiltered && (
          <button
            type="button"
            className="clear-filter-btn"
            onClick={() => onSelectReason('ALL')}
            disabled={isLoading}
            title="Reset to all reasons"
          >
            <XCircle size={14} />
            <span>Clear Filter</span>
          </button>
        )}
      </div>

      <div className="filter-counter-display">
        <span className="counter-text">
          {totalResults > 0 && filteredCount !== totalResults ? (
            <>
              Showing <strong>{filteredCount}</strong> of <strong>{totalResults}</strong> discrepancies
            </>
          ) : (
            <>
              Showing <strong>{filteredCount}</strong> {filteredCount === 1 ? 'discrepancy' : 'discrepancies'}
            </>
          )}
        </span>
      </div>
    </div>
  );
}
