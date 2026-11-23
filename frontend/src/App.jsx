import React, { useState, useEffect, useCallback, useRef } from 'react';
import Sidebar from './components/Sidebar';
import Header from './components/Header';
import SummaryCards from './components/SummaryCards';
import FilterBar from './components/FilterBar';
import ReconciliationTable from './components/ReconciliationTable';
import DetailsDrawer from './components/DetailsDrawer';
import { fetchDisagreements } from './services/api';

export default function App() {
  const [selectedOrg, setSelectedOrg] = useState('ORG-A');
  const [selectedReason, setSelectedReason] = useState('ALL');
  const [selectedSort, setSelectedSort] = useState('record_id');

  // Separate states for tenant-wide baseline (for summary cards) and filtered view (for table)
  const [summaryDisagreements, setSummaryDisagreements] = useState([]);
  const [displayedDisagreements, setDisplayedDisagreements] = useState([]);

  const [isLoading, setIsLoading] = useState(true);
  const [errorMessage, setErrorMessage] = useState(null);
  const [selectedRecord, setSelectedRecord] = useState(null);

  // Track the organization for which summaryDisagreements is currently loaded
  const currentSummaryOrgRef = useRef(null);

  // Load reconciliation data
  const loadData = useCallback(async (org, reason, sort, forceRefresh = false) => {
    setIsLoading(true);
    setErrorMessage(null);

    const isAllReason = !reason || reason.trim() === '' || reason === 'ALL';
    const isDefaultSort = !sort || sort.trim() === '' || sort === 'record_id';
    const needsSummaryFetch = forceRefresh || currentSummaryOrgRef.current !== org;

    try {
      if (isAllReason && isDefaultSort) {
        // Optimal path: A single API call satisfies both summary and table
        const data = await fetchDisagreements({ org, sort });
        const results = Array.isArray(data.results) ? data.results : [];
        setSummaryDisagreements(results);
        setDisplayedDisagreements(results);
        currentSummaryOrgRef.current = org;
      } else if (needsSummaryFetch) {
        // Org changed or refresh clicked while filter/sort is active:
        // Fetch unfiltered baseline for summary cards and filtered/sorted view for table
        const [summaryData, tableData] = await Promise.all([
          fetchDisagreements({ org }),
          fetchDisagreements({ org, reason, sort }),
        ]);

        const summaryResults = Array.isArray(summaryData.results) ? summaryData.results : [];
        const tableResults = Array.isArray(tableData.results) ? tableData.results : [];

        setSummaryDisagreements(summaryResults);
        setDisplayedDisagreements(tableResults);
        currentSummaryOrgRef.current = org;
      } else {
        // Reason filter or sort changed within the same organization:
        // Only fetch the filtered/sorted table data. Summary cards retain tenant-wide totals.
        const tableData = await fetchDisagreements({ org, reason, sort });
        const tableResults = Array.isArray(tableData.results) ? tableData.results : [];
        setDisplayedDisagreements(tableResults);
      }
    } catch (err) {
      setErrorMessage(err.message || 'Failed to load reconciliation records.');
      setDisplayedDisagreements([]);
    } finally {
      setIsLoading(false);
    }
  }, []);

  // Fetch data whenever org, reason, or sort changes
  useEffect(() => {
    let isCancelled = false;

    loadData(selectedOrg, selectedReason, selectedSort);

    return () => {
      isCancelled = true;
    };
  }, [loadData, selectedOrg, selectedReason, selectedSort]);

  // Handle Organization Change
  const handleSelectOrg = (newOrg) => {
    if (newOrg !== selectedOrg) {
      setSelectedOrg(newOrg);
      setSelectedRecord(null); // Close drawer if open on org switch
    }
  };

  // Handle Manual Refresh
  const handleRefresh = () => {
    loadData(selectedOrg, selectedReason, selectedSort, true);
  };

  return (
    <div className="app-container">
      {/* Deep Navy Sidebar */}
      <Sidebar activeNav="reconciliation" />

      {/* Main Viewport */}
      <div className="main-viewport">
        {/* Top Header */}
        <Header
          selectedOrg={selectedOrg}
          onSelectOrg={handleSelectOrg}
          onRefresh={handleRefresh}
          isLoading={isLoading}
        />

        {/* Content Body */}
        <main className="content-body">
          {/* 4 Metric Summary Cards (Always shows tenant-wide totals for selectedOrg) */}
          <SummaryCards
            disagreements={summaryDisagreements}
            isLoading={isLoading && summaryDisagreements.length === 0}
          />

          {/* Filter and Sorting Controls */}
          <FilterBar
            selectedReason={selectedReason}
            onSelectReason={setSelectedReason}
            selectedSort={selectedSort}
            onSelectSort={setSelectedSort}
            totalResults={summaryDisagreements.length}
            filteredCount={displayedDisagreements.length}
            isLoading={isLoading}
          />

          {/* Reconciliation Table (Shows filtered/sorted records) */}
          <ReconciliationTable
            disagreements={displayedDisagreements}
            isLoading={isLoading}
            errorMessage={errorMessage}
            onRetry={handleRefresh}
            onSelectRecord={setSelectedRecord}
            selectedRecordId={selectedRecord?.record_id}
          />
        </main>
      </div>

      {/* Slide-in Details Drawer */}
      {selectedRecord && (
        <DetailsDrawer
          disagreement={selectedRecord}
          onClose={() => setSelectedRecord(null)}
        />
      )}
    </div>
  );
}
