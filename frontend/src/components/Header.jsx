import React from 'react';
import { Building2, RefreshCw, ChevronDown } from 'lucide-react';

export default function Header({ 
  selectedOrg, 
  onSelectOrg, 
  onRefresh, 
  isLoading 
}) {
  return (
    <header className="dashboard-header">
      <div className="header-titles">
        <h1 className="header-title">Financial Reconciliation</h1>
        <p className="header-subtitle">
          Multi-tenant dealership ledger audit and settlement discrepancy engine
        </p>
      </div>

      <div className="header-actions">
        {/* Organization Selector */}
        <div className="org-selector-wrapper">
          <Building2 size={16} className="org-selector-icon" />
          <span className="org-selector-label">Organization:</span>
          <div className="org-tabs">
            <button
              type="button"
              className={`org-tab-btn ${selectedOrg === 'ORG-A' ? 'org-tab-active' : ''}`}
              onClick={() => onSelectOrg('ORG-A')}
              disabled={isLoading}
            >
              ORG-A
            </button>
            <button
              type="button"
              className={`org-tab-btn ${selectedOrg === 'ORG-B' ? 'org-tab-active' : ''}`}
              onClick={() => onSelectOrg('ORG-B')}
              disabled={isLoading}
            >
              ORG-B
            </button>
          </div>
        </div>

        {/* Global Refresh Button */}
        <button
          type="button"
          className="refresh-btn"
          onClick={onRefresh}
          disabled={isLoading}
          title="Refresh reconciliation data"
        >
          <RefreshCw size={15} className={`refresh-icon ${isLoading ? 'spinning' : ''}`} />
          <span>Refresh</span>
        </button>
      </div>
    </header>
  );
}
