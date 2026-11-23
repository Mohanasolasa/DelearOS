import React from 'react';
import { 
  Eye, 
  ArrowRight, 
  ShieldAlert, 
  FileSpreadsheet, 
  AlertCircle 
} from 'lucide-react';
import StatusBadge from './StatusBadge';
import { 
  formatCurrencyINR, 
  formatDifferenceINR, 
  formatDate 
} from '../utils/formatters';

export default function ReconciliationTable({
  disagreements = [],
  isLoading = false,
  errorMessage = null,
  onRetry,
  onSelectRecord,
  selectedRecordId,
}) {
  if (errorMessage) {
    return (
      <div className="table-state-box error-state-box">
        <AlertCircle size={36} className="error-icon" />
        <h3 className="state-title">Unable to Load Disagreements</h3>
        <p className="state-subtitle">{errorMessage}</p>
        {onRetry && (
          <button type="button" className="retry-btn" onClick={onRetry}>
            Retry Request
          </button>
        )}
      </div>
    );
  }

  if (isLoading) {
    return (
      <div className="table-wrapper">
        <table className="reconciliation-table">
          <thead>
            <tr>
              <th>Record ID</th>
              <th>Discrepancy Type</th>
              <th>Location (A &rarr; B)</th>
              <th className="th-right">System A Value</th>
              <th className="th-right">System B Value</th>
              <th className="th-right">Variance</th>
              <th>Dates (A / B)</th>
              <th className="th-center">Action</th>
            </tr>
          </thead>
          <tbody>
            {[1, 2, 3, 4, 5, 6].map((i) => (
              <tr key={i} className="skeleton-row">
                <td><div className="skeleton-bar w-24" /></td>
                <td><div className="skeleton-bar w-32" /></td>
                <td><div className="skeleton-bar w-28" /></td>
                <td><div className="skeleton-bar w-24 ml-auto" /></td>
                <td><div className="skeleton-bar w-24 ml-auto" /></td>
                <td><div className="skeleton-bar w-20 ml-auto" /></td>
                <td><div className="skeleton-bar w-24" /></td>
                <td><div className="skeleton-bar w-16 mx-auto" /></td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    );
  }

  if (!disagreements || disagreements.length === 0) {
    return (
      <div className="table-state-box empty-state-box">
        <FileSpreadsheet size={40} className="empty-icon" />
        <h3 className="state-title">No Disagreements Found</h3>
        <p className="state-subtitle">
          No reconciliation discrepancies match the selected organization and filter criteria.
        </p>
      </div>
    );
  }

  return (
    <div className="table-wrapper">
      <table className="reconciliation-table">
        <thead>
          <tr>
            <th>Record ID</th>
            <th>Discrepancy Type</th>
            <th>Dealership Location</th>
            <th className="th-right">System A Total</th>
            <th className="th-right">System B Total</th>
            <th className="th-right">Variance (Diff)</th>
            <th>Event / Settlement Date</th>
            <th className="th-center">Action</th>
          </tr>
        </thead>
        <tbody>
          {disagreements.map((d, idx) => {
            const isSelected = selectedRecordId === d.record_id;
            const diffNum = d.difference !== null ? parseFloat(d.difference) : null;
            
            // Determine difference pill styling
            let diffClass = 'diff-neutral';
            if (diffNum !== null) {
              if (diffNum < 0) diffClass = 'diff-negative';
              else if (diffNum > 0) diffClass = 'diff-positive';
            }

            // Check if System B location is redacted (null on a location mismatch)
            const isBLocationRedacted = 
              d.reason === 'LOCATION_MISMATCH' && !d.system_b_location;

            return (
              <tr 
                key={d.record_id || `orphan-${idx}`} 
                className={`table-row ${isSelected ? 'row-active' : ''}`}
                onClick={() => onSelectRecord(d)}
                tabIndex={0}
                onKeyDown={(e) => {
                  if (e.key === 'Enter') onSelectRecord(d);
                }}
              >
                {/* Record ID */}
                <td className="td-record-id">
                  <span className="record-id-chip">
                    {d.record_id || '—'}
                  </span>
                </td>

                {/* Reason Badge */}
                <td>
                  <StatusBadge reason={d.reason} />
                </td>

                {/* Location Comparison */}
                <td>
                  <div className="location-cell">
                    <span className="loc-tag loc-a">
                      {d.system_a_location || '—'}
                    </span>
                    <ArrowRight size={12} className="loc-arrow" />
                    {isBLocationRedacted ? (
                      <span className="loc-tag loc-redacted" title="Cross-tenant dealership location restricted">
                        <ShieldAlert size={11} className="mr-1" />
                        Restricted
                      </span>
                    ) : (
                      <span className="loc-tag loc-b">
                        {d.system_b_location || '—'}
                      </span>
                    )}
                  </div>
                </td>

                {/* System A Value */}
                <td className="td-amount">
                  <span className="amount-val">
                    {formatCurrencyINR(d.system_a_total_value)}
                  </span>
                </td>

                {/* System B Value */}
                <td className="td-amount">
                  <span className={`amount-val ${d.system_b_value === null ? 'val-null' : ''}`}>
                    {formatCurrencyINR(d.system_b_value)}
                  </span>
                </td>

                {/* Variance / Difference */}
                <td className="td-amount">
                  {d.difference !== null ? (
                    <span className={`diff-badge ${diffClass}`}>
                      {formatDifferenceINR(d.difference)}
                    </span>
                  ) : (
                    <span className="val-null">—</span>
                  )}
                </td>

                {/* Date */}
                <td>
                  <div className="date-cell">
                    <span className="date-primary">{formatDate(d.system_a_date)}</span>
                    {d.system_b_date && d.system_b_date !== d.system_a_date && (
                      <span className="date-secondary">B: {formatDate(d.system_b_date)}</span>
                    )}
                  </div>
                </td>

                {/* Action */}
                <td className="td-center">
                  <button
                    type="button"
                    className="view-btn"
                    onClick={(e) => {
                      e.stopPropagation();
                      onSelectRecord(d);
                    }}
                    title="View details"
                  >
                    <Eye size={14} />
                    <span>View</span>
                  </button>
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
