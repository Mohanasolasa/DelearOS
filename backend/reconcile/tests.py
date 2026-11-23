from decimal import Decimal
import pytest
from django.conf import settings
from django.db import IntegrityError
from django.db.models import ProtectedError

from reconcile.models import Location, SystemARecord, SystemBEntry


def test_django_setup_and_apps():
    """Verify that core settings, DRF, CORS, and reconcile apps are properly configured."""
    assert 'rest_framework' in settings.INSTALLED_APPS
    assert 'corsheaders' in settings.INSTALLED_APPS
    assert 'reconcile' in settings.INSTALLED_APPS
    assert settings.DATABASES['default']['ENGINE'] == 'django.db.backends.sqlite3'


@pytest.mark.django_db
class TestLocationModel:
    def test_location_creation_and_str(self):
        loc = Location.objects.create(
            location_id="LOC-101",
            org_id="ORG-A",
            name="Location 101"
        )
        assert loc.pk is not None
        assert loc.location_id == "LOC-101"
        assert loc.org_id == "ORG-A"
        assert loc.name == "Location 101"
        assert str(loc) == "LOC-101 - Location 101 (ORG-A)"

    def test_location_unique_constraint(self):
        Location.objects.create(
            location_id="LOC-101",
            org_id="ORG-A",
            name="Location 101"
        )
        with pytest.raises(IntegrityError):
            Location.objects.create(
                location_id="LOC-101",
                org_id="ORG-B",
                name="Duplicate Location"
            )


@pytest.mark.django_db
class TestSystemARecordModel:
    def test_system_a_record_creation_and_relationships(self):
        loc = Location.objects.create(
            location_id="LOC-201",
            org_id="ORG-B",
            name="Location 201"
        )
        rec = SystemARecord.objects.create(
            record_id="REC-1001",
            location=loc,
            event_date="2026-04-03",
            category_code="CAT-02",
            actor_id="USR-22",
            base_value=Decimal("69507.75"),
            adjustment=Decimal("19462.17"),
            total_value=Decimal("88969.92"),
            state="CONFIRMED"
        )
        assert rec.pk is not None
        assert rec.location == loc
        assert rec.location.org_id == "ORG-B"
        # Test reverse relationship through related_name
        assert loc.system_a_records.count() == 1
        assert loc.system_a_records.first() == rec
        assert "REC-1001" in str(rec)
        assert "88969.92" in str(rec)

    def test_system_a_record_unique_constraint(self):
        loc = Location.objects.create(location_id="LOC-101", org_id="ORG-A", name="Loc")
        SystemARecord.objects.create(
            record_id="REC-1001",
            location=loc,
            category_code="CAT-01",
            state="CONFIRMED"
        )
        with pytest.raises(IntegrityError):
            SystemARecord.objects.create(
                record_id="REC-1001",
                location=loc,
                category_code="CAT-02",
                state="CONFIRMED"
            )

    def test_system_a_nullable_fields_and_dirty_row_survival(self):
        """
        Dirty rows with unresolved locations, invalid dates, or empty actors
        must survive importing without database rejection.
        """
        dirty_rec = SystemARecord.objects.create(
            record_id="REC-DIRTY-1",
            location=None,
            location_raw="LOC-999-UNRESOLVED",
            event_date=None,
            event_date_raw="INVALID-DATE-2026",
            category_code="CAT-03",
            actor_id=None,
            base_value_raw="CORRUPTED_BASE",
            base_value=None,
            adjustment_raw="--",
            adjustment=None,
            total_value_raw="CORRUPTED_TOTAL",
            total_value=None,
            state="CONFIRMED"
        )
        assert dirty_rec.pk is not None
        assert dirty_rec.location is None
        assert dirty_rec.location_raw == "LOC-999-UNRESOLVED"
        assert dirty_rec.event_date is None
        assert dirty_rec.event_date_raw == "INVALID-DATE-2026"
        assert dirty_rec.actor_id is None
        assert dirty_rec.base_value is None
        assert dirty_rec.base_value_raw == "CORRUPTED_BASE"
        assert dirty_rec.adjustment_raw == "--"
        assert dirty_rec.total_value_raw == "CORRUPTED_TOTAL"

    def test_system_a_raw_monetary_fields_preservation(self):
        """
        Verify that original unparseable or dirty monetary strings from CSV
        (e.g., currency symbols, comma separators, or textual annotations)
        are preserved in base_value_raw, adjustment_raw, and total_value_raw.
        """
        rec = SystemARecord.objects.create(
            record_id="REC-RAW-1",
            category_code="CAT-05",
            base_value_raw="$1,25,000.50",
            base_value=None,
            adjustment_raw="N/A",
            adjustment=None,
            total_value_raw="PENDING",
            total_value=None,
            state="CONFIRMED"
        )
        assert rec.pk is not None
        assert rec.base_value_raw == "$1,25,000.50"
        assert rec.base_value is None
        assert rec.adjustment_raw == "N/A"
        assert rec.adjustment is None
        assert rec.total_value_raw == "PENDING"
        assert rec.total_value is None


@pytest.mark.django_db
class TestSystemBEntryModel:
    def test_system_b_entry_creation_and_relationships(self):
        loc = Location.objects.create(
            location_id="LOC-201",
            org_id="ORG-B",
            name="Location 201"
        )
        entry = SystemBEntry.objects.create(
            entry_id="ENT/2026/4001",
            record_ref_raw="REC-1001",
            record_ref="REC-1001",
            location=loc,
            recorded_on="2026-04-03",
            value_raw="88969.92",
            value=Decimal("88969.92"),
            label="Entry for CAT-02"
        )
        assert entry.pk is not None
        assert entry.location == loc
        assert entry.location.org_id == "ORG-B"
        # Test reverse relationship
        assert loc.system_b_entries.count() == 1
        assert loc.system_b_entries.first() == entry
        assert "ENT/2026/4001" in str(entry)
        assert "REC-1001" in str(entry)

    def test_system_b_entry_unique_constraint(self):
        loc = Location.objects.create(location_id="LOC-101", org_id="ORG-A", name="Loc")
        SystemBEntry.objects.create(
            entry_id="ENT/2026/4001",
            record_ref_raw="REC-1001",
            location=loc
        )
        with pytest.raises(IntegrityError):
            SystemBEntry.objects.create(
                entry_id="ENT/2026/4001",
                record_ref_raw="REC-1002",
                location=loc
            )

    def test_system_b_non_unique_record_ref(self):
        """
        Multiple System B entries may reference the same System A record (split/adjustment).
        record_ref must NOT have a unique constraint.
        """
        loc = Location.objects.create(location_id="LOC-101", org_id="ORG-A", name="Loc")
        entry1 = SystemBEntry.objects.create(
            entry_id="ENT/2026/4001",
            record_ref_raw="REC-1001",
            record_ref="REC-1001",
            location=loc,
            value=Decimal("50000.00")
        )
        entry2 = SystemBEntry.objects.create(
            entry_id="ENT/2026/4002",
            record_ref_raw="REC-1001",
            record_ref="REC-1001",
            location=loc,
            value=Decimal("38969.92")
        )
        assert entry1.record_ref == entry2.record_ref
        assert SystemBEntry.objects.filter(record_ref="REC-1001").count() == 2

    def test_system_b_nullable_fields_and_dirty_row_survival(self):
        """
        Dirty rows with missing values or non-standard formatting must survive.
        For example: value='' or value='1,25,400.00' and raw ref ' REC - 1070 '.
        """
        dirty_entry = SystemBEntry.objects.create(
            entry_id="ENT/2026/4050",
            record_ref_raw=" REC - 1070 ",
            record_ref="REC-1070",
            location=None,
            location_raw="LOC-999-MISSING",
            recorded_on=None,
            recorded_on_raw="2026/03/20",
            value_raw="1,25,400.00",
            value=None,
            label="Entry with unparsed formatted value"
        )
        assert dirty_entry.pk is not None
        assert dirty_entry.value is None
        assert dirty_entry.value_raw == "1,25,400.00"
        assert dirty_entry.record_ref_raw == " REC - 1070 "
        assert dirty_entry.record_ref == "REC-1070"
        assert dirty_entry.location is None
        assert dirty_entry.location_raw == "LOC-999-MISSING"

    def test_no_foreign_key_between_system_b_and_system_a(self):
        """
        Verify that SystemBEntry does not require a SystemARecord to exist,
        and there is no FK connecting SystemBEntry to SystemARecord.
        """
        # Ensure 0 System A records exist
        assert SystemARecord.objects.count() == 0

        # System B entry can still be created and persisted independently
        entry = SystemBEntry.objects.create(
            entry_id="ENT/2026/9999",
            record_ref_raw="REC-NONEXISTENT",
            record_ref="REC-NONEXISTENT",
            value=Decimal("1000.00")
        )
        assert entry.pk is not None
        assert SystemBEntry.objects.count() == 1

        # Check model fields to confirm no ForeignKey to SystemARecord exists
        b_fields = [f.name for f in SystemBEntry._meta.get_fields()]
        assert "record_id" not in b_fields
        # Confirm 'record_ref' is a CharField, not a ForeignKey
        record_ref_field = SystemBEntry._meta.get_field("record_ref")
        assert record_ref_field.get_internal_type() == "CharField"

    def test_location_protected_on_delete(self):
        """
        Deleting a Location referenced by SystemARecord or SystemBEntry
        must raise ProtectedError to prevent orphaned records.
        """
        loc = Location.objects.create(location_id="LOC-101", org_id="ORG-A", name="Loc")
        SystemARecord.objects.create(
            record_id="REC-1001",
            location=loc,
            category_code="CAT-01",
            state="CONFIRMED"
        )
        with pytest.raises(ProtectedError):
            loc.delete()


@pytest.mark.django_db
class TestCSVImporter:
    def test_successful_location_import(self):
        from django.core.management import call_command
        call_command('import_data')

        assert Location.objects.count() == 5
        loc101 = Location.objects.get(location_id="LOC-101")
        assert loc101.org_id == "ORG-A"
        assert loc101.name == "Location 101"

        loc201 = Location.objects.get(location_id="LOC-201")
        assert loc201.org_id == "ORG-B"
        assert loc201.name == "Location 201"

    def test_successful_system_a_import(self):
        from django.core.management import call_command
        call_command('import_data')

        assert SystemARecord.objects.count() == 120
        rec1001 = SystemARecord.objects.get(record_id="REC-1001")
        assert rec1001.location.location_id == "LOC-201"
        assert rec1001.location_raw == "LOC-201"
        assert str(rec1001.event_date) == "2026-04-03"
        assert rec1001.category_code == "CAT-02"
        assert rec1001.actor_id == "USR-22"
        assert rec1001.base_value == Decimal("69507.75")
        assert rec1001.adjustment == Decimal("19462.17")
        assert rec1001.total_value == Decimal("88969.92")
        assert rec1001.state == "CONFIRMED"

    def test_successful_system_b_import(self):
        from django.core.management import call_command
        call_command('import_data')

        assert SystemBEntry.objects.count() == 121
        entry1 = SystemBEntry.objects.get(entry_id="ENT/2026/4001")
        assert entry1.record_ref == "REC-1001"
        assert entry1.location.location_id == "LOC-201"
        assert str(entry1.recorded_on) == "2026-04-03"
        assert entry1.value == Decimal("88969.92")
        assert entry1.label == "Entry for CAT-02"

    def test_blank_monetary_values(self):
        from django.core.management import call_command
        call_command('import_data')

        # Row 49 in system_b.csv (ENT/2026/4050) has empty value=''
        entry = SystemBEntry.objects.get(entry_id="ENT/2026/4050")
        assert entry.value is None
        assert entry.value != Decimal('0')
        assert entry.value_raw == ""
        assert entry.record_ref == "REC-1050"
        assert entry.location.location_id == "LOC-202"

    def test_indian_style_comma_amounts(self):
        from django.core.management import call_command
        call_command('import_data')

        # Row 62 in system_b.csv (ENT/2026/4064) has value='1,25,400.00'
        entry = SystemBEntry.objects.get(entry_id="ENT/2026/4064")
        assert entry.value == Decimal("125400.00")
        assert entry.value_raw == "1,25,400.00"

    def test_messy_reference_normalization(self):
        from django.core.management import call_command
        from reconcile.management.commands.import_data import normalize_record_ref

        # Unit verification of normalization logic
        assert normalize_record_ref("rec1034") == "REC-1034"
        assert normalize_record_ref("REC - 1070") == "REC-1070"
        assert normalize_record_ref("1112") == "REC-1112"
        assert normalize_record_ref("REC-1001") == "REC-1001"
        assert normalize_record_ref("rec_1002") == "REC-1002"
        assert normalize_record_ref("") is None
        assert normalize_record_ref(None) is None

        call_command('import_data')

        # Row 68 in system_b.csv has ' REC - 1070 '
        entry = SystemBEntry.objects.get(entry_id="ENT/2026/4070")
        assert entry.record_ref == "REC-1070"
        assert entry.record_ref_raw == " REC - 1070 "

    def test_invalid_dates_handled_safely(self, tmp_path):
        import csv
        from django.core.management import call_command

        loc_file = tmp_path / "locations.csv"
        sys_a_file = tmp_path / "system_a.csv"
        sys_b_file = tmp_path / "system_b.csv"

        with open(loc_file, "w", newline="") as f:
            w = csv.writer(f)
            w.writerow(["location_id", "org_id", "location_name"])
            w.writerow(["LOC-101", "ORG-A", "Location 101"])

        with open(sys_a_file, "w", newline="") as f:
            w = csv.writer(f)
            w.writerow(["record_id", "location_id", "event_date", "category_code", "actor_id", "base_value", "adjustment", "total_value", "state"])
            w.writerow(["REC-BAD-DATE", "LOC-101", "NOT-A-DATE", "CAT-01", "USR-1", "100.00", "10.00", "110.00", "CONFIRMED"])

        with open(sys_b_file, "w", newline="") as f:
            w = csv.writer(f)
            w.writerow(["entry_id", "record_ref", "location_id", "recorded_on", "value", "label"])
            w.writerow(["ENT-BAD-DATE", "REC-BAD-DATE", "LOC-101", "2026/99/99", "110.00", "Bad date entry"])

        call_command('import_data', data_dir=str(tmp_path))

        rec = SystemARecord.objects.get(record_id="REC-BAD-DATE")
        assert rec.event_date is None
        assert rec.event_date_raw == "NOT-A-DATE"

        entry = SystemBEntry.objects.get(entry_id="ENT-BAD-DATE")
        assert entry.recorded_on is None
        assert entry.recorded_on_raw == "2026/99/99"

    def test_unknown_locations_handled_safely(self, tmp_path):
        import csv
        from django.core.management import call_command

        loc_file = tmp_path / "locations.csv"
        sys_a_file = tmp_path / "system_a.csv"
        sys_b_file = tmp_path / "system_b.csv"

        with open(loc_file, "w", newline="") as f:
            w = csv.writer(f)
            w.writerow(["location_id", "org_id", "location_name"])
            w.writerow(["LOC-101", "ORG-A", "Location 101"])

        with open(sys_a_file, "w", newline="") as f:
            w = csv.writer(f)
            w.writerow(["record_id", "location_id", "event_date", "category_code", "actor_id", "base_value", "adjustment", "total_value", "state"])
            w.writerow(["REC-UNK-LOC", "LOC-UNKNOWN", "2026-04-01", "CAT-01", "USR-1", "100.00", "0.00", "100.00", "CONFIRMED"])

        with open(sys_b_file, "w", newline="") as f:
            w = csv.writer(f)
            w.writerow(["entry_id", "record_ref", "location_id", "recorded_on", "value", "label"])
            w.writerow(["ENT-UNK-LOC", "REC-UNK-LOC", "LOC-MISSING", "2026-04-01", "100.00", "Unknown location entry"])

        call_command('import_data', data_dir=str(tmp_path))

        rec = SystemARecord.objects.get(record_id="REC-UNK-LOC")
        assert rec.location is None
        assert rec.location_raw == "LOC-UNKNOWN"

        entry = SystemBEntry.objects.get(entry_id="ENT-UNK-LOC")
        assert entry.location is None
        assert entry.location_raw == "LOC-MISSING"

    def test_orphan_entries_imported(self):
        from django.core.management import call_command
        call_command('import_data')

        # Check total System B count is 121
        assert SystemBEntry.objects.count() == 121
        # Check System A records count is 120
        assert SystemARecord.objects.count() == 120

        # System B has 121 records, which means there is at least 1 orphan or extra entry
        sys_a_record_ids = set(SystemARecord.objects.values_list('record_id', flat=True))
        b_refs = set(SystemBEntry.objects.values_list('record_ref', flat=True))
        orphan_refs = b_refs - sys_a_record_ids

        # All B entries exist in DB regardless of whether their reference is in System A
        assert len(b_refs) > 0
        for entry in SystemBEntry.objects.all():
            assert entry.entry_id.startswith("ENT/2026/")

    def test_idempotency_by_running_importer_twice(self):
        from django.core.management import call_command
        from reconcile.management.commands.import_data import Command

        call_command('import_data')
        loc_count1 = Location.objects.count()
        a_count1 = SystemARecord.objects.count()
        b_count1 = SystemBEntry.objects.count()

        assert loc_count1 == 5
        assert a_count1 == 120
        assert b_count1 == 121

        # Run second time
        call_command('import_data')
        loc_count2 = Location.objects.count()
        a_count2 = SystemARecord.objects.count()
        b_count2 = SystemBEntry.objects.count()

        # Counts must be completely identical
        assert loc_count2 == loc_count1 == 5
        assert a_count2 == a_count1 == 120
        assert b_count2 == b_count1 == 121

        # On second run, 0 records should be created and all records should be updated
        stats2 = Command.last_stats
        assert stats2['locations']['created'] == 0
        assert stats2['locations']['updated'] == 5
        assert stats2['system_a']['created'] == 0
        assert stats2['system_a']['updated'] == 120
        assert stats2['system_b']['created'] == 0
        assert stats2['system_b']['updated'] == 121

    def test_original_raw_value_preservation(self):
        from django.core.management import call_command
        call_command('import_data')

        rec = SystemARecord.objects.get(record_id="REC-1001")
        assert rec.base_value_raw == "69507.75"
        assert rec.adjustment_raw == "19462.17"
        assert rec.total_value_raw == "88969.92"
        assert rec.location_raw == "LOC-201"
        assert rec.event_date_raw == "2026-04-03"

        entry = SystemBEntry.objects.get(entry_id="ENT/2026/4001")
        assert entry.value_raw == "88969.92"
        assert entry.record_ref_raw == "REC-1001"
        assert entry.location_raw == "LOC-201"
        assert entry.recorded_on_raw == "2026-04-03"

    def test_import_failure_reporting(self, tmp_path):
        import csv
        from unittest.mock import patch
        from django.core.management import call_command

        loc_file = tmp_path / "locations.csv"
        sys_a_file = tmp_path / "system_a.csv"
        sys_b_file = tmp_path / "system_b.csv"

        with open(loc_file, "w", newline="") as f:
            w = csv.writer(f)
            w.writerow(["location_id", "org_id", "location_name"])
            w.writerow(["LOC-101", "ORG-A", "Location 101"])

        with open(sys_a_file, "w", newline="") as f:
            w = csv.writer(f)
            w.writerow(["record_id", "location_id", "event_date", "category_code", "actor_id", "base_value", "adjustment", "total_value", "state"])
            w.writerow(["REC-OK-1", "LOC-101", "2026-04-01", "CAT-01", "USR-1", "100.00", "0.00", "100.00", "CONFIRMED"])
            w.writerow(["REC-FAIL", "LOC-101", "2026-04-01", "CAT-01", "USR-1", "100.00", "0.00", "100.00", "CONFIRMED"])
            w.writerow(["REC-OK-2", "LOC-101", "2026-04-01", "CAT-01", "USR-1", "100.00", "0.00", "100.00", "CONFIRMED"])

        with open(sys_b_file, "w", newline="") as f:
            w = csv.writer(f)
            w.writerow(["entry_id", "record_ref", "location_id", "recorded_on", "value", "label"])

        orig_update_or_create = SystemARecord.objects.update_or_create

        def mock_update_or_create(*args, **kwargs):
            if kwargs.get('record_id') == 'REC-FAIL':
                raise IntegrityError("Simulated database failure on REC-FAIL")
            return orig_update_or_create(*args, **kwargs)

        with patch.object(SystemARecord.objects, 'update_or_create', side_effect=mock_update_or_create):
            from reconcile.management.commands.import_data import Command
            call_command('import_data', data_dir=str(tmp_path))
            stats = Command.last_stats

        # REC-OK-1 and REC-OK-2 should be saved, while REC-FAIL reports an error
        assert stats['system_a']['saved'] == 2
        assert stats['system_a']['failed'] == 1
        assert len(stats['system_a']['errors']) == 1
        assert "REC-FAIL" in stats['system_a']['errors'][0]
        assert SystemARecord.objects.filter(record_id="REC-OK-1").exists()
        assert SystemARecord.objects.filter(record_id="REC-OK-2").exists()
        assert not SystemARecord.objects.filter(record_id="REC-FAIL").exists()

