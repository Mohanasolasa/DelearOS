"""
Reconciliation Engine for DealerOS.

Compares System A records against System B entries and detects discrepancies:
- MISSING_IN_B: Eligible active System A records absent from System B
- ORPHAN_IN_B: System B entries referencing non-existent System A records
- DUPLICATE_IN_B: Multiple System B entries referencing one System A record with incorrect sum
- VALUE_MISMATCH: Single entry value mismatch or incomplete/blank monetary values
- LOCATION_MISMATCH: Different dealership locations between systems
- DATE_MISMATCH: Discrepant event dates when both dates are present
- VOIDED_IN_B: VOIDED System A record erroneously billed/entered in System B
"""

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from typing import Dict, List, Optional, Set, Any, Iterable

from reconcile.models import Location, SystemARecord, SystemBEntry


# Disagreement Classification Constants
REASON_MISSING_IN_B = "MISSING_IN_B"
REASON_ORPHAN_IN_B = "ORPHAN_IN_B"
REASON_DUPLICATE_IN_B = "DUPLICATE_IN_B"
REASON_VALUE_MISMATCH = "VALUE_MISMATCH"
REASON_LOCATION_MISMATCH = "LOCATION_MISMATCH"
REASON_DATE_MISMATCH = "DATE_MISMATCH"
REASON_VOIDED_IN_B = "VOIDED_IN_B"


@dataclass
class Disagreement:
    """
    Structured representation of a reconciliation discrepancy.
    Maintains Decimal arithmetic, exact date objects, and rich context
    for serialization in subsequent API and frontend dashboard layers.
    """
    reason: str
    record_id: Optional[str]
    system_a_location: Optional[str] = None
    system_b_location: Optional[str] = None
    system_b_locations: List[str] = field(default_factory=list)
    system_a_date: Optional[date] = None
    system_b_date: Optional[date] = None
    system_b_dates: List[date] = field(default_factory=list)
    system_a_total_value: Optional[Decimal] = None
    system_b_value: Optional[Decimal] = None
    system_b_values: List[Optional[Decimal]] = field(default_factory=list)
    difference: Optional[Decimal] = None
    system_b_entry_ids: List[str] = field(default_factory=list)
    explanation: str = ""

    def to_dict(self) -> Dict[str, Any]:
        """Convert disagreement to a cleanly serializable dictionary."""
        return {
            "reason": self.reason,
            "record_id": self.record_id,
            "system_a_location": self.system_a_location,
            "system_b_location": self.system_b_location,
            "system_b_locations": self.system_b_locations,
            "system_a_date": self.system_a_date.isoformat() if self.system_a_date else None,
            "system_b_date": self.system_b_date.isoformat() if self.system_b_date else None,
            "system_b_dates": [d.isoformat() for d in self.system_b_dates if d],
            "system_a_total_value": str(self.system_a_total_value) if self.system_a_total_value is not None else None,
            "system_b_value": str(self.system_b_value) if self.system_b_value is not None else None,
            "system_b_values": [str(v) if v is not None else None for v in self.system_b_values],
            "difference": str(self.difference) if self.difference is not None else None,
            "system_b_entry_ids": self.system_b_entry_ids,
            "explanation": self.explanation,
        }


def get_location_identifier(obj: Any) -> Optional[str]:
    """Helper to retrieve location ID from a model instance or raw fallback."""
    if not obj:
        return None
    if getattr(obj, 'location', None):
        return obj.location.location_id
    raw = getattr(obj, 'location_raw', None)
    return str(raw).strip() if raw else None


class ReconciliationEngine:
    """
    Core reconciliation service engine.
    Compares System A records against System B entries with zero HTTP/view coupling.
    """

    def __init__(
        self,
        system_a_records: Optional[Iterable[SystemARecord]] = None,
        system_b_entries: Optional[Iterable[SystemBEntry]] = None
    ):
        self._a_records = system_a_records
        self._b_entries = system_b_entries

    def _get_records(self):
        if self._a_records is not None:
            a_records = list(self._a_records)
        else:
            a_records = list(SystemARecord.objects.select_related('location').all())

        if self._b_entries is not None:
            b_entries = list(self._b_entries)
        else:
            b_entries = list(SystemBEntry.objects.select_related('location').all())

        return a_records, b_entries

    def reconcile(self) -> List[Disagreement]:
        """
        Executes the reconciliation algorithm and returns a sorted, deterministic
        list of Disagreement objects.
        """
        a_records, b_entries = self._get_records()
        disagreements: List[Disagreement] = []

        # 1. Index System B entries by normalized record_ref
        b_by_ref: Dict[str, List[SystemBEntry]] = defaultdict(list)
        orphan_entries_no_ref: List[SystemBEntry] = []

        for b in b_entries:
            ref = b.record_ref
            if ref and str(ref).strip():
                b_by_ref[str(ref).strip()].append(b)
            else:
                orphan_entries_no_ref.append(b)

        # 2. Index System A records by record_id
        a_by_id: Dict[str, SystemARecord] = {a.record_id: a for a in a_records}
        seen_b_refs: Set[str] = set()

        # 3. Evaluate each System A record
        for a in a_records:
            rec_id = a.record_id
            entries = b_by_ref.get(rec_id, [])
            seen_b_refs.add(rec_id)

            a_loc = get_location_identifier(a)
            a_date = a.event_date

            # CASE 3.1: No System B entries exist
            if not entries:
                # VOIDED Policy: Do not report MISSING_IN_B for VOIDED records
                if a.state == "VOIDED":
                    continue

                disagreements.append(Disagreement(
                    reason=REASON_MISSING_IN_B,
                    record_id=rec_id,
                    system_a_location=a_loc,
                    system_a_date=a_date,
                    system_a_total_value=a.total_value,
                    explanation=f"Record {rec_id} exists in System A ({a.state}) with total {a.total_value} but has no corresponding System B entries."
                ))
                continue

            # Context extraction for entries
            b_entry_ids = [e.entry_id for e in entries]
            b_locs = [get_location_identifier(e) for e in entries if get_location_identifier(e)]
            b_primary_loc = b_locs[0] if b_locs else None
            b_dates = [e.recorded_on for e in entries if e.recorded_on]
            b_primary_date = b_dates[0] if b_dates else None
            b_values = [e.value for e in entries]

            # CASE 3.2: VOIDED Record Policy
            # If a VOIDED System A record has entries in System B, flag as VOIDED_IN_B
            if a.state == "VOIDED":
                has_values = any(v is not None for v in b_values)
                b_sum = sum(v for v in b_values if v is not None) if has_values else None
                disagreements.append(Disagreement(
                    reason=REASON_VOIDED_IN_B,
                    record_id=rec_id,
                    system_a_location=a_loc,
                    system_b_location=b_primary_loc,
                    system_b_locations=b_locs,
                    system_a_date=a_date,
                    system_b_date=b_primary_date,
                    system_b_dates=b_dates,
                    system_a_total_value=a.total_value,
                    system_b_value=b_sum,
                    system_b_values=b_values,
                    difference=b_sum if b_sum is not None else None,
                    system_b_entry_ids=b_entry_ids,
                    explanation=f"System A record {rec_id} is marked VOIDED, but {len(entries)} entry/entries were entered in System B."
                ))
                # Skip normal monetary evaluation for VOIDED records
                continue

            # CASE 3.3: Monetary Reconciliation for Active Records
            if len(entries) == 1:
                b_entry = entries[0]
                b_val = b_entry.value
                if b_val is None:
                    # Missing/blank monetary value in System B (Never treat None as zero)
                    disagreements.append(Disagreement(
                        reason=REASON_VALUE_MISMATCH,
                        record_id=rec_id,
                        system_a_location=a_loc,
                        system_b_location=get_location_identifier(b_entry),
                        system_b_locations=[get_location_identifier(b_entry)] if get_location_identifier(b_entry) else [],
                        system_a_date=a_date,
                        system_b_date=b_entry.recorded_on,
                        system_b_dates=[b_entry.recorded_on] if b_entry.recorded_on else [],
                        system_a_total_value=a.total_value,
                        system_b_value=None,
                        system_b_values=[None],
                        difference=None,
                        system_b_entry_ids=[b_entry.entry_id],
                        explanation=f"System B entry {b_entry.entry_id} has a missing or unparseable monetary value (System A total is {a.total_value})."
                    ))
                elif a.total_value is None:
                    disagreements.append(Disagreement(
                        reason=REASON_VALUE_MISMATCH,
                        record_id=rec_id,
                        system_a_location=a_loc,
                        system_b_location=get_location_identifier(b_entry),
                        system_b_locations=[get_location_identifier(b_entry)] if get_location_identifier(b_entry) else [],
                        system_a_date=a_date,
                        system_b_date=b_entry.recorded_on,
                        system_b_dates=[b_entry.recorded_on] if b_entry.recorded_on else [],
                        system_a_total_value=None,
                        system_b_value=b_val,
                        system_b_values=[b_val],
                        difference=None,
                        system_b_entry_ids=[b_entry.entry_id],
                        explanation=f"System A record {rec_id} has a missing monetary total_value (System B has {b_val})."
                    ))
                elif b_val != a.total_value:
                    diff = b_val - a.total_value
                    disagreements.append(Disagreement(
                        reason=REASON_VALUE_MISMATCH,
                        record_id=rec_id,
                        system_a_location=a_loc,
                        system_b_location=get_location_identifier(b_entry),
                        system_b_locations=[get_location_identifier(b_entry)] if get_location_identifier(b_entry) else [],
                        system_a_date=a_date,
                        system_b_date=b_entry.recorded_on,
                        system_b_dates=[b_entry.recorded_on] if b_entry.recorded_on else [],
                        system_a_total_value=a.total_value,
                        system_b_value=b_val,
                        system_b_values=[b_val],
                        difference=diff,
                        system_b_entry_ids=[b_entry.entry_id],
                        explanation=f"Value mismatch for record {rec_id}: System A total is {a.total_value}, System B value is {b_val} (difference: {diff:+})."
                    ))
            else:
                # Multiple System B entries referencing one System A record
                has_none = any(e.value is None for e in entries)
                if has_none:
                    # Incomplete group: Cannot sum if any entry is missing
                    disagreements.append(Disagreement(
                        reason=REASON_VALUE_MISMATCH,
                        record_id=rec_id,
                        system_a_location=a_loc,
                        system_b_location=b_primary_loc,
                        system_b_locations=b_locs,
                        system_a_date=a_date,
                        system_b_date=b_primary_date,
                        system_b_dates=b_dates,
                        system_a_total_value=a.total_value,
                        system_b_value=None,
                        system_b_values=b_values,
                        difference=None,
                        system_b_entry_ids=b_entry_ids,
                        explanation=f"Multiple System B entries exist for record {rec_id}, but one or more entries have missing monetary values."
                    ))
                elif a.total_value is None:
                    b_sum = sum(e.value for e in entries)
                    disagreements.append(Disagreement(
                        reason=REASON_VALUE_MISMATCH,
                        record_id=rec_id,
                        system_a_location=a_loc,
                        system_b_location=b_primary_loc,
                        system_b_locations=b_locs,
                        system_a_date=a_date,
                        system_b_date=b_primary_date,
                        system_b_dates=b_dates,
                        system_a_total_value=None,
                        system_b_value=b_sum,
                        system_b_values=b_values,
                        difference=None,
                        system_b_entry_ids=b_entry_ids,
                        explanation=f"System A record {rec_id} has no total_value to compare with System B entries."
                    ))
                else:
                    b_sum = sum(e.value for e in entries)
                    if b_sum != a.total_value:
                        diff = b_sum - a.total_value
                        disagreements.append(Disagreement(
                            reason=REASON_DUPLICATE_IN_B,
                            record_id=rec_id,
                            system_a_location=a_loc,
                            system_b_location=b_primary_loc,
                            system_b_locations=b_locs,
                            system_a_date=a_date,
                            system_b_date=b_primary_date,
                            system_b_dates=b_dates,
                            system_a_total_value=a.total_value,
                            system_b_value=b_sum,
                            system_b_values=b_values,
                            difference=diff,
                            system_b_entry_ids=b_entry_ids,
                            explanation=f"Multiple System B entries for record {rec_id} sum to {b_sum}, differing from System A total {a.total_value} (difference: {diff:+})."
                        ))
                    # Else: b_sum == a.total_value -> Valid split entry, no duplicate discrepancy!

            # CASE 3.4: Independent Location Mismatch Check
            if a_loc:
                for b_entry in entries:
                    b_loc = get_location_identifier(b_entry)
                    if b_loc and b_loc != a_loc:
                        disagreements.append(Disagreement(
                            reason=REASON_LOCATION_MISMATCH,
                            record_id=rec_id,
                            system_a_location=a_loc,
                            system_b_location=b_loc,
                            system_b_locations=[b_loc],
                            system_a_date=a_date,
                            system_b_date=b_entry.recorded_on,
                            system_b_dates=[b_entry.recorded_on] if b_entry.recorded_on else [],
                            system_a_total_value=a.total_value,
                            system_b_value=b_entry.value,
                            system_b_values=[b_entry.value],
                            system_b_entry_ids=[b_entry.entry_id],
                            explanation=f"Location mismatch on record {rec_id}: System A location is {a_loc}, but System B entry {b_entry.entry_id} has location {b_loc}."
                        ))

            # CASE 3.5: Independent Date Mismatch Check
            if a_date:
                for b_entry in entries:
                    b_date = b_entry.recorded_on
                    # Compare only when both dates are present and differ
                    if b_date and b_date != a_date:
                        disagreements.append(Disagreement(
                            reason=REASON_DATE_MISMATCH,
                            record_id=rec_id,
                            system_a_location=a_loc,
                            system_b_location=get_location_identifier(b_entry),
                            system_b_locations=[get_location_identifier(b_entry)] if get_location_identifier(b_entry) else [],
                            system_a_date=a_date,
                            system_b_date=b_date,
                            system_b_dates=[b_date],
                            system_a_total_value=a.total_value,
                            system_b_value=b_entry.value,
                            system_b_values=[b_entry.value],
                            system_b_entry_ids=[b_entry.entry_id],
                            explanation=f"Date mismatch on record {rec_id}: System A event_date is {a_date}, but System B entry {b_entry.entry_id} has recorded_on {b_date}."
                        ))

        # 4. Check for Orphan Entries in System B (references not in System A)
        for ref, entries in b_by_ref.items():
            if ref not in a_by_id:
                for b_entry in entries:
                    b_loc = get_location_identifier(b_entry)
                    disagreements.append(Disagreement(
                        reason=REASON_ORPHAN_IN_B,
                        record_id=ref,
                        system_a_location=None,
                        system_b_location=b_loc,
                        system_b_locations=[b_loc] if b_loc else [],
                        system_a_date=None,
                        system_b_date=b_entry.recorded_on,
                        system_b_dates=[b_entry.recorded_on] if b_entry.recorded_on else [],
                        system_a_total_value=None,
                        system_b_value=b_entry.value,
                        system_b_values=[b_entry.value],
                        system_b_entry_ids=[b_entry.entry_id],
                        explanation=f"System B entry {b_entry.entry_id} references nonexistent System A record '{ref}'."
                    ))

        # System B entries with no record reference at all
        for b_entry in orphan_entries_no_ref:
            b_loc = get_location_identifier(b_entry)
            disagreements.append(Disagreement(
                reason=REASON_ORPHAN_IN_B,
                record_id=b_entry.record_ref_raw or None,
                system_a_location=None,
                system_b_location=b_loc,
                system_b_locations=[b_loc] if b_loc else [],
                system_a_date=None,
                system_b_date=b_entry.recorded_on,
                system_b_dates=[b_entry.recorded_on] if b_entry.recorded_on else [],
                system_a_total_value=None,
                system_b_value=b_entry.value,
                system_b_values=[b_entry.value],
                system_b_entry_ids=[b_entry.entry_id],
                explanation=f"System B entry {b_entry.entry_id} has no valid record reference."
            ))

        # 5. Deterministic sorting
        disagreements.sort(
            key=lambda d: (
                d.record_id or "",
                d.reason,
                d.system_b_entry_ids[0] if d.system_b_entry_ids else ""
            )
        )

        return disagreements

    def get_summary(self) -> Dict[str, Any]:
        """Provides a statistical summary of the reconciliation results."""
        disagreements = self.reconcile()
        counts_by_reason: Dict[str, int] = defaultdict(int)
        for d in disagreements:
            counts_by_reason[d.reason] += 1

        return {
            "total_disagreements": len(disagreements),
            "by_reason": dict(counts_by_reason),
            "disagreements": disagreements,
        }


def reconcile(
    system_a_records: Optional[Iterable[SystemARecord]] = None,
    system_b_entries: Optional[Iterable[SystemBEntry]] = None
) -> List[Disagreement]:
    """Convenience functional interface for reconciliation."""
    engine = ReconciliationEngine(system_a_records, system_b_entries)
    return engine.reconcile()
