import React from 'react';
import { 
  AlertCircle, 
  HelpCircle, 
  Copy, 
  DollarSign, 
  MapPin, 
  Calendar, 
  Ban, 
  Info 
} from 'lucide-react';

const BADGE_CONFIG = {
  MISSING_IN_B: {
    label: 'Missing in B',
    bg: '#fffbeb',
    text: '#b45309',
    border: '#fde68a',
    Icon: AlertCircle,
  },
  ORPHAN_IN_B: {
    label: 'Orphan Entry',
    bg: '#ecfeff',
    text: '#0e7490',
    border: '#a5f3fc',
    Icon: HelpCircle,
  },
  DUPLICATE_IN_B: {
    label: 'Duplicate in B',
    bg: '#faf5ff',
    text: '#7e22ce',
    border: '#e9d5ff',
    Icon: Copy,
  },
  VALUE_MISMATCH: {
    label: 'Value Mismatch',
    bg: '#fef2f2',
    text: '#b91c1c',
    border: '#fecaca',
    Icon: DollarSign,
  },
  LOCATION_MISMATCH: {
    label: 'Location Mismatch',
    bg: '#eff6ff',
    text: '#1d4ed8',
    border: '#bfdbfe',
    Icon: MapPin,
  },
  DATE_MISMATCH: {
    label: 'Date Mismatch',
    bg: '#f8fafc',
    text: '#475569',
    border: '#cbd5e1',
    Icon: Calendar,
  },
  VOIDED_IN_B: {
    label: 'Voided in B',
    bg: '#f4f4f5',
    text: '#3f3f46',
    border: '#e4e4e7',
    Icon: Ban,
  },
};

export default function StatusBadge({ reason, size = 'normal' }) {
  const config = BADGE_CONFIG[reason] || {
    label: reason || 'Unknown',
    bg: '#f1f5f9',
    text: '#475569',
    border: '#e2e8f0',
    Icon: Info,
  };

  const { label, bg, text, border, Icon } = config;

  return (
    <span
      className={`status-badge ${size === 'small' ? 'status-badge-sm' : ''}`}
      style={{
        backgroundColor: bg,
        color: text,
        borderColor: border,
      }}
    >
      <Icon className="status-badge-icon" size={size === 'small' ? 12 : 13} />
      <span>{label}</span>
    </span>
  );
}
