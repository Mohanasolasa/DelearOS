import React from 'react';
import { 
  AlertOctagon, 
  FileQuestion, 
  Scale, 
  Copy 
} from 'lucide-react';

export default function SummaryCards({ disagreements = [], isLoading = false }) {
  // Compute metric numbers directly from actual API response data
  const totalCount = disagreements.length;
  
  const missingCount = disagreements.filter(
    (d) => d.reason === 'MISSING_IN_B'
  ).length;

  const valueMismatchCount = disagreements.filter(
    (d) => d.reason === 'VALUE_MISMATCH'
  ).length;

  const duplicateCount = disagreements.filter(
    (d) => d.reason === 'DUPLICATE_IN_B'
  ).length;

  const cards = [
    {
      id: 'total',
      title: 'Total Disagreements',
      count: totalCount,
      description: 'Audit records requiring resolution',
      Icon: AlertOctagon,
      accentColor: '#4f46e5',
      accentBg: '#eef2ff',
    },
    {
      id: 'missing',
      title: 'Missing in System B',
      count: missingCount,
      description: 'Active records absent from B',
      Icon: FileQuestion,
      accentColor: '#d97706',
      accentBg: '#fffbeb',
    },
    {
      id: 'values',
      title: 'Value Mismatches',
      count: valueMismatchCount,
      description: 'Settlement amount variances',
      Icon: Scale,
      accentColor: '#dc2626',
      accentBg: '#fef2f2',
    },
    {
      id: 'duplicates',
      title: 'Duplicate Entries',
      count: duplicateCount,
      description: 'Multiple B entries with sum variance',
      Icon: Copy,
      accentColor: '#7c3aed',
      accentBg: '#faf5ff',
    },
  ];

  return (
    <div className="summary-cards-grid">
      {cards.map((card) => {
        const { id, title, count, description, Icon, accentColor, accentBg } = card;
        return (
          <div key={id} className="summary-card">
            <div className="summary-card-header">
              <span className="summary-card-title">{title}</span>
              <div 
                className="summary-card-icon-wrapper" 
                style={{ backgroundColor: accentBg, color: accentColor }}
              >
                <Icon size={18} />
              </div>
            </div>
            <div className="summary-card-body">
              {isLoading ? (
                <div className="metric-skeleton" />
              ) : (
                <span className="summary-card-metric">{count}</span>
              )}
            </div>
            <div className="summary-card-footer">
              <span className="summary-card-desc">{description}</span>
            </div>
          </div>
        );
      })}
    </div>
  );
}
