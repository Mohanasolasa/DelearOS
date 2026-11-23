import React from 'react';
import { 
  FileSpreadsheet, 
  LayoutDashboard, 
  Layers, 
  ShieldCheck, 
  Sparkles 
} from 'lucide-react';

export default function Sidebar({ activeNav = 'reconciliation' }) {
  return (
    <aside className="dashboard-sidebar">
      <div className="sidebar-brand">
        <div className="brand-logo-container">
          <Layers className="brand-icon" size={20} />
        </div>
        <div className="brand-info">
          <span className="brand-name">DealerOS</span>
          <span className="brand-badge">Enterprise</span>
        </div>
      </div>

      <div className="sidebar-section">
        <span className="sidebar-section-title">FINANCIAL AUDIT</span>
        <nav className="sidebar-nav">
          <div 
            className={`nav-item ${activeNav === 'overview' ? 'nav-item-active' : 'nav-item-disabled'}`}
            title="Overview dashboard"
          >
            <LayoutDashboard size={18} className="nav-icon" />
            <span className="nav-label">Overview</span>
            <span className="nav-badge-pill">Soon</span>
          </div>

          <div 
            className={`nav-item ${activeNav === 'reconciliation' ? 'nav-item-active' : ''}`}
            title="Reconciliation workbench"
          >
            <FileSpreadsheet size={18} className="nav-icon" />
            <span className="nav-label">Reconciliation</span>
            <div className="nav-active-pill" />
          </div>
        </nav>
      </div>

      <div className="sidebar-spacer" />

      <div className="sidebar-footer">
        <div className="connection-status">
          <span className="status-dot-pulse" />
          <span className="status-text">Engine Online</span>
        </div>
        <div className="version-info">
          <span>DealerOS v1.0.0</span>
          <span className="version-tag">Production</span>
        </div>
      </div>
    </aside>
  );
}
