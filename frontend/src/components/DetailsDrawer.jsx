import React, { useEffect } from 'react';
import { 
  X, 
  ShieldAlert, 
  Calendar, 
  MapPin, 
  FileText, 
  Layers, 
  ArrowRight,
  TrendingDown,
  TrendingUp,
  AlertTriangle
} from 'lucide-react';
import StatusBadge from './StatusBadge';
import { 
  formatDetailsCurrency, 
  formatDifferenceINR, 
  formatDate 
} from '../utils/formatters';

export default function DetailsDrawer({ disagreement, onClose }) {
  // Close drawer on Escape key press
  useEffect(() => {
    function handleKeyDown(e) {
      if (e.key === 'Escape') {
        onClose();
      }
    }
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [onClose]);

  if (!disagreement) return null;

  const {
    record_id,
    reason,
    explanation,
    system_a_location,
    system_b_location,
    system_a_date,
    system_b_date,
    system_a_total_value,
    system_b_value,
    difference,
    system_b_entry_ids = [],
  } = disagreement;

  const isBLocationRedacted = reason === 'LOCATION_MISMATCH' && !system_b_location;
  const diffNum = difference !== null ? parseFloat(difference) : null;

  return (
    <div className="drawer-overlay" onClick={onClose}>
      <aside 
        className="drawer-panel" 
        onClick={(e) => e.stopPropagation()}
        role="dialog"
        aria-modal="true"
        aria-labelledby="drawer-title"
      >
        {/* Drawer Header */}
        <div className="drawer-header">
          <div className="drawer-header-content">
            <span className="drawer-subtitle">DISAGREEMENT AUDIT</span>
            <h2 id="drawer-title" className="drawer-title">
              {record_id || 'Orphan System B Record'}
            </h2>
          </div>
          <div className="drawer-header-actions">
            <StatusBadge reason={reason} />
            <button
              type="button"
              className="drawer-close-btn"
              onClick={onClose}
              aria-label="Close drawer"
            >
              <X size={18} />
            </button>
          </div>
        </div>

        {/* Drawer Body */}
        <div className="drawer-body">
          {/* Audit Explanation Banner */}
          <div className="audit-callout-card">
            <div className="audit-callout-header">
              <AlertTriangle size={16} className="audit-callout-icon" />
              <span className="audit-callout-title">Audit Diagnostic</span>
            </div>
            <p className="audit-callout-text">{explanation || 'No explanation provided.'}</p>
          </div>

          {/* Section 1: Financial Settlement Comparison */}
          <div className="drawer-section">
            <h3 className="section-title">
              <FileText size={16} className="section-icon" />
              <span>Financial Settlement Variance</span>
            </h3>

            <div className="settlement-comparison-grid">
              {/* System A Card */}
              <div className="metric-box metric-box-sysa">
                <span className="metric-box-label">System A Total Value</span>
                <span className="metric-box-value">
                  {formatDetailsCurrency(system_a_total_value)}
                </span>
                <span className="metric-box-sub">Canonical ledger amount</span>
              </div>

              {/* System B Card */}
              <div className="metric-box metric-box-sysb">
                <span className="metric-box-label">System B Total Value</span>
                <span className={`metric-box-value ${system_b_value === null ? 'val-null' : ''}`}>
                  {formatDetailsCurrency(system_b_value)}
                </span>
                <span className="metric-box-sub">Reported billing entry</span>
              </div>
            </div>

            {/* Variance Net Calculation */}
            <div className="variance-net-banner">
              <div className="variance-info">
                <span className="variance-label">Net Ledger Variance (Difference)</span>
                <span className="variance-sub">
                  Calculated as System B total minus System A total
                </span>
              </div>
              <div className="variance-value-wrapper">
                {diffNum !== null ? (
                  <span className={`variance-badge ${diffNum < 0 ? 'var-neg' : diffNum > 0 ? 'var-pos' : 'var-zero'}`}>
                    {diffNum < 0 && <TrendingDown size={14} className="mr-1" />}
                    {diffNum > 0 && <TrendingUp size={14} className="mr-1" />}
                    {formatDifferenceINR(difference)}
                  </span>
                ) : (
                  <span className="variance-badge var-unavailable">Unavailable</span>
                )}
              </div>
            </div>
          </div>

          {/* Section 2: Dealership Location Audit */}
          <div className="drawer-section">
            <h3 className="section-title">
              <MapPin size={16} className="section-icon" />
              <span>Dealership Facility Audit</span>
            </h3>

            <div className="facility-comparison-row">
              <div className="facility-card">
                <span className="facility-label">System A Facility</span>
                <span className="facility-id">{system_a_location || '—'}</span>
              </div>

              <div className="facility-arrow">
                <ArrowRight size={18} />
              </div>

              <div className="facility-card">
                <span className="facility-label">System B Facility</span>
                {isBLocationRedacted ? (
                  <div className="facility-restricted" title="Security policy: Redacted across tenant boundaries">
                    <ShieldAlert size={14} className="mr-1" />
                    <span>Restricted (Cross-Tenant)</span>
                  </div>
                ) : (
                  <span className="facility-id">{system_b_location || '—'}</span>
                )}
              </div>
            </div>
          </div>

          {/* Section 3: Event & Settlement Dates */}
          <div className="drawer-section">
            <h3 className="section-title">
              <Calendar size={16} className="section-icon" />
              <span>Transaction & Settlement Timeline</span>
            </h3>

            <div className="timeline-grid">
              <div className="timeline-item">
                <span className="timeline-label">System A Event Date</span>
                <span className="timeline-val">{formatDate(system_a_date)}</span>
              </div>
              <div className="timeline-item">
                <span className="timeline-label">System B Recorded Date</span>
                <span className="timeline-val">{formatDate(system_b_date)}</span>
              </div>
            </div>
          </div>

          {/* Section 4: Linked System B Audit Entries */}
          <div className="drawer-section">
            <h3 className="section-title">
              <Layers size={16} className="section-icon" />
              <span>Linked System B Entries ({system_b_entry_ids.length})</span>
            </h3>

            {system_b_entry_ids.length > 0 ? (
              <div className="entry-ids-list">
                {system_b_entry_ids.map((entryId) => (
                  <div key={entryId} className="entry-chip">
                    <span className="entry-id-text">{entryId}</span>
                  </div>
                ))}
              </div>
            ) : (
              <p className="no-entries-text">No corresponding System B entries recorded.</p>
            )}
          </div>
        </div>

        {/* Drawer Footer */}
        <div className="drawer-footer">
          <button type="button" className="drawer-footer-btn" onClick={onClose}>
            Close Inspector
          </button>
        </div>
      </aside>
    </div>
  );
}
