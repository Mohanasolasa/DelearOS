from datetime import date
from decimal import Decimal
import pytest

from reconcile.models import Location, SystemARecord, SystemBEntry
from reconcile.services.reconciliation import (
    ReconciliationEngine,
    reconcile,
    REASON_MISSING_IN_B,
    REASON_ORPHAN_IN_B,
    REASON_DUPLICATE_IN_B,
    REASON_VALUE_MISMATCH,
    REASON_LOCATION_MISMATCH,
    REASON_DATE_MISMATCH,
    REASON_VOIDED_IN_B,
)


@pytest.mark.django_db
class TestReconciliationEngine:
    """
    Exhaustive test suite for the reconciliation engine covering all 18 requirements.
    """

    @pytest.fixture
    def locations(self):
        loc1 = Location.objects.create(location_id="LOC-101", org_id="ORG-A", name="Location 101")
        loc2 = Location.objects.create(location_id="LOC-201", org_id="ORG-B", name="Location 201")
        return {"LOC-101": loc1, "LOC-201": loc2}

    def test_matching_records_with_identical_values(self, locations):
        """1. Matching records with identical values, locations, and dates should have no disagreements."""
        loc = locations["LOC-101"]
        SystemARecord.objects.create(
            record_id="REC-TEST-1",
            location=loc,
            event_date=date(2026, 4, 1),
            total_value=Decimal("50000.00"),
            state="CONFIRMED"
        )
        SystemBEntry.objects.create(
            entry_id="ENT-TEST-1",
            record_ref="REC-TEST-1",
            record_ref_raw="REC-TEST-1",
            location=loc,
            recorded_on=date(2026, 4, 1),
            value=Decimal("50000.00"),
            value_raw="50000.00"
        )

        disagreements = reconcile()
        assert len(disagreements) == 0

    def test_missing_system_b_records(self, locations):
        """2. An eligible System A record with no System B entry is flagged as MISSING_IN_B."""
        loc = locations["LOC-101"]
        SystemARecord.objects.create(
            record_id="REC-MISSING-1",
            location=loc,
            event_date=date(2026, 4, 2),
            total_value=Decimal("41095.33"),
            state="CONFIRMED"
        )

        disagreements = reconcile()
        assert len(disagreements) == 1
        d = disagreements[0]
        assert d.reason == REASON_MISSING_IN_B
        assert d.record_id == "REC-MISSING-1"
        assert d.system_a_total_value == Decimal("41095.33")
        assert d.system_a_location == "LOC-101"
        assert d.system_a_date == date(2026, 4, 2)
        assert d.system_b_entry_ids == []

    def test_orphan_system_b_entries(self, locations):
        """3. A System B entry referencing a nonexistent System A record is flagged as ORPHAN_IN_B."""
        loc = locations["LOC-201"]
        SystemBEntry.objects.create(
            entry_id="ENT-ORPHAN-1",
            record_ref="REC-NONEXISTENT",
            record_ref_raw="REC-NONEXISTENT",
            location=loc,
            recorded_on=date(2026, 3, 18),
            value=Decimal("41250.00"),
            value_raw="41250.00"
        )

        disagreements = reconcile()
        assert len(disagreements) == 1
        d = disagreements[0]
        assert d.reason == REASON_ORPHAN_IN_B
        assert d.record_id == "REC-NONEXISTENT"
        assert d.system_b_value == Decimal("41250.00")
        assert d.system_b_location == "LOC-201"
        assert d.system_b_entry_ids == ["ENT-ORPHAN-1"]

    def test_single_entry_value_mismatch(self, locations):
        """4. Single System B entry with a different monetary amount is flagged as VALUE_MISMATCH."""
        loc = locations["LOC-101"]
        SystemARecord.objects.create(
            record_id="REC-VAL-1",
            location=loc,
            event_date=date(2026, 4, 3),
            total_value=Decimal("121388.01"),
            state="CONFIRMED"
        )
        SystemBEntry.objects.create(
            entry_id="ENT-VAL-1",
            record_ref="REC-VAL-1",
            location=loc,
            recorded_on=date(2026, 4, 3),
            value=Decimal("94834.38"),
            value_raw="94834.38"
        )

        disagreements = reconcile()
        assert len(disagreements) == 1
        d = disagreements[0]
        assert d.reason == REASON_VALUE_MISMATCH
        assert d.record_id == "REC-VAL-1"
        assert d.system_a_total_value == Decimal("121388.01")
        assert d.system_b_value == Decimal("94834.38")
        assert d.difference == Decimal("-26553.63")
        assert d.system_b_entry_ids == ["ENT-VAL-1"]

    def test_duplicate_system_b_entries(self, locations):
        """5. Multiple System B entries that differ from System A total are classified as DUPLICATE_IN_B."""
        loc = locations["LOC-101"]
        SystemARecord.objects.create(
            record_id="REC-DUP-1",
            location=loc,
            event_date=date(2026, 3, 4),
            total_value=Decimal("112837.06"),
            state="CONFIRMED"
        )
        SystemBEntry.objects.create(
            entry_id="ENT-DUP-1",
            record_ref="REC-DUP-1",
            location=loc,
            recorded_on=date(2026, 3, 4),
            value=Decimal("112837.06"),
            value_raw="112837.06"
        )
        SystemBEntry.objects.create(
            entry_id="ENT-DUP-2",
            record_ref="REC-DUP-1",
            location=loc,
            recorded_on=date(2026, 3, 4),
            value=Decimal("112837.06"),
            value_raw="112837.06"
        )

        disagreements = reconcile()
        assert len(disagreements) == 1
        d = disagreements[0]
        assert d.reason == REASON_DUPLICATE_IN_B
        assert d.record_id == "REC-DUP-1"
        assert d.system_a_total_value == Decimal("112837.06")
        assert d.system_b_value == Decimal("225674.12")
        assert d.difference == Decimal("112837.06")
        assert set(d.system_b_entry_ids) == {"ENT-DUP-1", "ENT-DUP-2"}

    def test_valid_split_entries(self, locations):
        """6. Multiple System B entries summing exactly to System A total are valid splits and NOT duplicates."""
        loc = locations["LOC-101"]
        SystemARecord.objects.create(
            record_id="REC-SPLIT-1",
            location=loc,
            event_date=date(2026, 3, 14),
            total_value=Decimal("1000.00"),
            state="CONFIRMED"
        )
        SystemBEntry.objects.create(
            entry_id="ENT-SPLIT-1",
            record_ref="REC-SPLIT-1",
            location=loc,
            recorded_on=date(2026, 3, 14),
            value=Decimal("400.00"),
            value_raw="400.00"
        )
        SystemBEntry.objects.create(
            entry_id="ENT-SPLIT-2",
            record_ref="REC-SPLIT-1",
            location=loc,
            recorded_on=date(2026, 3, 14),
            value=Decimal("600.00"),
            value_raw="600.00"
        )

        disagreements = reconcile()
        assert len(disagreements) == 0

    def test_split_entries_not_summing_to_system_a_total(self, locations):
        """7. Split entries that do not sum to the System A total are classified as DUPLICATE_IN_B."""
        loc = locations["LOC-101"]
        SystemARecord.objects.create(
            record_id="REC-SPLIT-BAD",
            location=loc,
            event_date=date(2026, 3, 14),
            total_value=Decimal("1000.00"),
            state="CONFIRMED"
        )
        SystemBEntry.objects.create(
            entry_id="ENT-SB-1",
            record_ref="REC-SPLIT-BAD",
            location=loc,
            recorded_on=date(2026, 3, 14),
            value=Decimal("400.00"),
            value_raw="400.00"
        )
        SystemBEntry.objects.create(
            entry_id="ENT-SB-2",
            record_ref="REC-SPLIT-BAD",
            location=loc,
            recorded_on=date(2026, 3, 14),
            value=Decimal("550.00"),
            value_raw="550.00"
        )

        disagreements = reconcile()
        assert len(disagreements) == 1
        d = disagreements[0]
        assert d.reason == REASON_DUPLICATE_IN_B
        assert d.record_id == "REC-SPLIT-BAD"
        assert d.system_a_total_value == Decimal("1000.00")
        assert d.system_b_value == Decimal("950.00")
        assert d.difference == Decimal("-50.00")

    def test_blank_system_b_monetary_value(self, locations):
        """8. Blank System B monetary value (None) is never treated as zero, reports VALUE_MISMATCH with difference=None."""
        loc = locations["LOC-101"]
        SystemARecord.objects.create(
            record_id="REC-BLANK-VAL",
            location=loc,
            event_date=date(2026, 3, 20),
            total_value=Decimal("160405.85"),
            state="CONFIRMED"
        )
        SystemBEntry.objects.create(
            entry_id="ENT-BLANK-VAL",
            record_ref="REC-BLANK-VAL",
            location=loc,
            recorded_on=date(2026, 3, 20),
            value=None,
            value_raw=""
        )

        disagreements = reconcile()
        assert len(disagreements) == 1
        d = disagreements[0]
        assert d.reason == REASON_VALUE_MISMATCH
        assert d.record_id == "REC-BLANK-VAL"
        assert d.system_b_value is None
        assert d.difference is None
        assert d.system_b_entry_ids == ["ENT-BLANK-VAL"]

    def test_messy_references_already_normalized(self, locations):
        """9. Normalized references (e.g. REC-1070 from ' REC - 1070 ') match cleanly without disagreement."""
        loc = locations["LOC-101"]
        SystemARecord.objects.create(
            record_id="REC-1070",
            location=loc,
            event_date=date(2026, 3, 18),
            total_value=Decimal("1608.95"),
            state="CONFIRMED"
        )
        SystemBEntry.objects.create(
            entry_id="ENT-4070",
            record_ref="REC-1070",
            record_ref_raw=" REC - 1070 ",
            location=loc,
            recorded_on=date(2026, 3, 18),
            value=Decimal("1608.95"),
            value_raw="1608.95"
        )

        disagreements = reconcile()
        assert len(disagreements) == 0

    def test_location_mismatch(self, locations):
        """10. Flag differing location identifiers while preserving both values."""
        loc1 = locations["LOC-101"]
        loc2 = locations["LOC-201"]
        SystemARecord.objects.create(
            record_id="REC-LOC-DIFF",
            location=loc1,
            event_date=date(2026, 3, 19),
            total_value=Decimal("83361.40"),
            state="CONFIRMED"
        )
        SystemBEntry.objects.create(
            entry_id="ENT-LOC-DIFF",
            record_ref="REC-LOC-DIFF",
            location=loc2,
            recorded_on=date(2026, 3, 19),
            value=Decimal("83361.40"),
            value_raw="83361.40"
        )

        disagreements = reconcile()
        assert len(disagreements) == 1
        d = disagreements[0]
        assert d.reason == REASON_LOCATION_MISMATCH
        assert d.record_id == "REC-LOC-DIFF"
        assert d.system_a_location == "LOC-101"
        assert d.system_b_location == "LOC-201"
        assert d.system_b_entry_ids == ["ENT-LOC-DIFF"]

    def test_date_mismatch(self, locations):
        """11. Flag differing dates when both are available while preserving both dates."""
        loc = locations["LOC-101"]
        SystemARecord.objects.create(
            record_id="REC-DATE-DIFF",
            location=loc,
            event_date=date(2026, 3, 31),
            total_value=Decimal("111699.30"),
            state="CONFIRMED"
        )
        SystemBEntry.objects.create(
            entry_id="ENT-DATE-DIFF",
            record_ref="REC-DATE-DIFF",
            location=loc,
            recorded_on=date(2026, 4, 2),
            value=Decimal("111699.30"),
            value_raw="111699.30"
        )

        disagreements = reconcile()
        assert len(disagreements) == 1
        d = disagreements[0]
        assert d.reason == REASON_DATE_MISMATCH
        assert d.record_id == "REC-DATE-DIFF"
        assert d.system_a_date == date(2026, 3, 31)
        assert d.system_b_date == date(2026, 4, 2)
        assert d.system_b_entry_ids == ["ENT-DATE-DIFF"]

    def test_voided_record_with_no_b_entry(self, locations):
        """12. A VOIDED record with no System B entry is NOT reported as MISSING_IN_B."""
        loc = locations["LOC-101"]
        SystemARecord.objects.create(
            record_id="REC-VOID-NO-B",
            location=loc,
            event_date=date(2026, 4, 5),
            total_value=Decimal("50000.00"),
            state="VOIDED"
        )

        disagreements = reconcile()
        assert len(disagreements) == 0

    def test_voided_record_with_b_entry(self, locations):
        """13. A VOIDED record with a System B entry reports VOIDED_IN_B and not ordinary value/dup mismatch."""
        loc = locations["LOC-101"]
        SystemARecord.objects.create(
            record_id="REC-VOID-WITH-B",
            location=loc,
            event_date=date(2026, 4, 5),
            total_value=Decimal("57092.35"),
            state="VOIDED"
        )
        SystemBEntry.objects.create(
            entry_id="ENT-VOID-1",
            record_ref="REC-VOID-WITH-B",
            location=loc,
            recorded_on=date(2026, 4, 5),
            value=Decimal("57092.35"),
            value_raw="57092.35"
        )

        disagreements = reconcile()
        assert len(disagreements) == 1
        d = disagreements[0]
        assert d.reason == REASON_VOIDED_IN_B
        assert d.record_id == "REC-VOID-WITH-B"
        assert d.system_b_entry_ids == ["ENT-VOID-1"]

    def test_multiple_independent_disagreements_on_one_record(self, locations):
        """14. A record with value, location, and date differences reports all three independently."""
        loc1 = locations["LOC-101"]
        loc2 = locations["LOC-201"]
        SystemARecord.objects.create(
            record_id="REC-MULTI-DIFF",
            location=loc1,
            event_date=date(2026, 3, 1),
            total_value=Decimal("100.00"),
            state="CONFIRMED"
        )
        SystemBEntry.objects.create(
            entry_id="ENT-MULTI-DIFF",
            record_ref="REC-MULTI-DIFF",
            location=loc2,
            recorded_on=date(2026, 3, 5),
            value=Decimal("150.00"),
            value_raw="150.00"
        )

        disagreements = reconcile()
        assert len(disagreements) == 3
        reasons = [d.reason for d in disagreements]
        assert REASON_VALUE_MISMATCH in reasons
        assert REASON_LOCATION_MISMATCH in reasons
        assert REASON_DATE_MISMATCH in reasons

    def test_multiple_b_entries_with_one_blank_monetary_value(self, locations):
        """15. Multiple B entries where one has a blank monetary value reports VALUE_MISMATCH with difference=None."""
        loc = locations["LOC-101"]
        SystemARecord.objects.create(
            record_id="REC-GROUP-BLANK",
            location=loc,
            event_date=date(2026, 3, 10),
            total_value=Decimal("1000.00"),
            state="CONFIRMED"
        )
        SystemBEntry.objects.create(
            entry_id="ENT-GB-1",
            record_ref="REC-GROUP-BLANK",
            location=loc,
            recorded_on=date(2026, 3, 10),
            value=Decimal("400.00"),
            value_raw="400.00"
        )
        SystemBEntry.objects.create(
            entry_id="ENT-GB-2",
            record_ref="REC-GROUP-BLANK",
            location=loc,
            recorded_on=date(2026, 3, 10),
            value=None,
            value_raw=""
        )

        disagreements = reconcile()
        assert len(disagreements) == 1
        d = disagreements[0]
        assert d.reason == REASON_VALUE_MISMATCH
        assert d.difference is None
        assert d.system_b_value is None

    def test_missing_dates_do_not_produce_date_mismatch(self, locations):
        """16. When either date is missing (None), do not invent a DATE_MISMATCH."""
        loc = locations["LOC-101"]
        SystemARecord.objects.create(
            record_id="REC-NO-DATE",
            location=loc,
            event_date=None,
            total_value=Decimal("100.00"),
            state="CONFIRMED"
        )
        SystemBEntry.objects.create(
            entry_id="ENT-WITH-DATE",
            record_ref="REC-NO-DATE",
            location=loc,
            recorded_on=date(2026, 4, 1),
            value=Decimal("100.00"),
            value_raw="100.00"
        )

        disagreements = reconcile()
        # No disagreements because monetary and locations match, and date comparison is skipped when one is missing
        assert len(disagreements) == 0

    def test_missing_locations_do_not_produce_location_mismatch(self):
        """17. When location identifiers are unavailable, do not invent a LOCATION_MISMATCH."""
        SystemARecord.objects.create(
            record_id="REC-NO-LOC",
            location=None,
            location_raw="",
            event_date=date(2026, 4, 1),
            total_value=Decimal("100.00"),
            state="CONFIRMED"
        )
        SystemBEntry.objects.create(
            entry_id="ENT-NO-LOC",
            record_ref="REC-NO-LOC",
            location=None,
            location_raw="",
            recorded_on=date(2026, 4, 1),
            value=Decimal("100.00"),
            value_raw="100.00"
        )

        disagreements = reconcile()
        assert len(disagreements) == 0

    def test_decimal_precision_and_rounding_behavior(self, locations):
        """18. Verify strict Decimal precision where float would cause precision artifacts."""
        loc = locations["LOC-101"]
        # In float arithmetic: 0.1 + 0.2 != 0.3 (0.30000000000000004)
        # In Decimal arithmetic: Decimal('0.10') + Decimal('0.20') == Decimal('0.30')
        SystemARecord.objects.create(
            record_id="REC-DEC-1",
            location=loc,
            event_date=date(2026, 4, 1),
            total_value=Decimal("0.30"),
            state="CONFIRMED"
        )
        SystemBEntry.objects.create(
            entry_id="ENT-DEC-1",
            record_ref="REC-DEC-1",
            location=loc,
            recorded_on=date(2026, 4, 1),
            value=Decimal("0.10"),
            value_raw="0.10"
        )
        SystemBEntry.objects.create(
            entry_id="ENT-DEC-2",
            record_ref="REC-DEC-1",
            location=loc,
            recorded_on=date(2026, 4, 1),
            value=Decimal("0.20"),
            value_raw="0.20"
        )

        disagreements = reconcile()
        assert len(disagreements) == 0
