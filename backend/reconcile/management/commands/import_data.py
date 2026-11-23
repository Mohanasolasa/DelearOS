import csv
import os
import re
from datetime import datetime, date
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Optional, Dict, Any, Tuple

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from reconcile.models import Location, SystemARecord, SystemBEntry


def normalize_record_ref(raw_ref: Optional[str]) -> Optional[str]:
    """
    Normalize inconsistent record references from System B:
      rec1034 -> REC-1034
      REC - 1070 -> REC-1070
      1112 -> REC-1112
      REC-1001 -> REC-1001
    Returns None for empty/blank values, or normalized reference string.
    """
    if raw_ref is None:
        return None
    cleaned = str(raw_ref).strip()
    if not cleaned:
        return None

    # Pattern 1: Exact matches like '1112', 'rec1034', 'REC - 1070', 'REC-1001', 'rec_1002'
    match = re.search(r'^(?:rec[\s\-_]*)?(\d+)$', cleaned, re.IGNORECASE)
    if match:
        return f"REC-{match.group(1)}"

    # Pattern 2: Any string containing 'rec' followed by digits
    match2 = re.search(r'rec[\s\-_]*(\d+)', cleaned, re.IGNORECASE)
    if match2:
        return f"REC-{match2.group(1)}"

    # Fallback: uppercase stripped string
    return cleaned.upper()


def parse_decimal(val_str: Optional[str]) -> Optional[Decimal]:
    """
    Parses a string into a Decimal.
    Handles standard (125,400.00) and Indian (1,25,400.00) comma styles.
    Strips currency symbols ($ or ₹ or € or £) and extra spaces.
    Empty or blank values return None (never zero).
    Invalid/unparseable numbers return None.
    """
    if val_str is None:
        return None
    cleaned = str(val_str).strip()
    if not cleaned:
        return None

    # Strip currency symbols and whitespace
    cleaned = re.sub(r'[\$₹€£\s]', '', cleaned)
    # Remove commas
    cleaned = cleaned.replace(',', '')
    if not cleaned:
        return None

    try:
        return Decimal(cleaned)
    except (InvalidOperation, TypeError, ValueError):
        return None


def parse_date(date_str: Optional[str]) -> Optional[date]:
    """
    Parses a date string across common formats (%Y-%m-%d, %Y/%m/%d, %d-%m-%Y, etc.).
    Returns a date object or None if invalid or blank.
    """
    if not date_str:
        return None
    cleaned = str(date_str).strip()
    if not cleaned:
        return None

    formats = [
        "%Y-%m-%d",
        "%Y/%m/%d",
        "%d-%m-%Y",
        "%d/%m/%Y",
        "%m/%d/%Y",
        "%d.%m.%Y",
    ]
    for fmt in formats:
        try:
            return datetime.strptime(cleaned, fmt).date()
        except ValueError:
            continue
    return None


class Command(BaseCommand):
    help = "Imports automotive inventory datasets (locations, System A, System B) idempotently."

    def add_arguments(self, parser):
        parser.add_argument(
            '--data-dir',
            type=str,
            default=None,
            help='Directory containing locations.csv, system_a.csv, and system_b.csv (default: project root data/)'
        )
        parser.add_argument(
            '--locations-file',
            type=str,
            default=None,
            help='Explicit path to locations.csv'
        )
        parser.add_argument(
            '--system-a-file',
            type=str,
            default=None,
            help='Explicit path to system_a.csv'
        )
        parser.add_argument(
            '--system-b-file',
            type=str,
            default=None,
            help='Explicit path to system_b.csv'
        )
        parser.add_argument(
            '--silent',
            action='store_true',
            help='Suppress detailed step logging'
        )

    def handle(self, *args, **options):
        # Resolve data directory
        data_dir_arg = options.get('data_dir') or os.environ.get('DATA_DIR')
        if data_dir_arg:
            data_dir = Path(data_dir_arg).resolve()
        else:
            # Check multiple standard candidates:
            # 1. BASE_DIR.parent / 'data' (root data/ when BASE_DIR is backend/)
            # 2. BASE_DIR / 'data' (if data/ is located inside backend/)
            # 3. Path.cwd() / 'data' (if running from repo root)
            # 4. Path.cwd().parent / 'data' (if running from subfolder)
            candidates = [
                settings.BASE_DIR.parent / 'data',
                settings.BASE_DIR / 'data',
                Path.cwd() / 'data',
                Path.cwd().parent / 'data',
            ]
            data_dir = None
            for cand in candidates:
                if cand.is_dir() and (cand / 'locations.csv').is_file():
                    data_dir = cand.resolve()
                    break

            if not data_dir:
                data_dir = (settings.BASE_DIR.parent / 'data').resolve()

        locations_path = Path(options['locations_file']) if options.get('locations_file') else data_dir / 'locations.csv'
        system_a_path = Path(options['system_a_file']) if options.get('system_a_file') else data_dir / 'system_a.csv'
        system_b_path = Path(options['system_b_file']) if options.get('system_b_file') else data_dir / 'system_b.csv'

        self.stdout.write(self.style.MIGRATE_HEADING("DealerOS CSV Importer"))
        self.stdout.write(f"Source data directory: {data_dir}")

        overall_stats = {
            'locations': {},
            'system_a': {},
            'system_b': {},
        }

        # Step 1: Import Locations FIRST
        if not locations_path.exists():
            raise CommandError(f"Locations file not found at: {locations_path}")
        overall_stats['locations'] = self.import_locations(locations_path)

        # Preload resolved locations into an in-memory dictionary for fast, safe lookups
        locations_cache = {loc.location_id: loc for loc in Location.objects.all()}

        # Step 2: Import System A Records
        if not system_a_path.exists():
            raise CommandError(f"System A file not found at: {system_a_path}")
        overall_stats['system_a'] = self.import_system_a(system_a_path, locations_cache)

        # Step 3: Import System B Entries
        if not system_b_path.exists():
            raise CommandError(f"System B file not found at: {system_b_path}")
        overall_stats['system_b'] = self.import_system_b(system_b_path, locations_cache)

        # Print Final Comprehensive Summary
        self.print_summary(overall_stats)
        self.stats = overall_stats
        Command.last_stats = overall_stats
        return None

    def import_locations(self, filepath: Path) -> Dict[str, Any]:
        self.stdout.write(f"\nImporting Locations from: {filepath.name}...")
        stats = {
            'read': 0,
            'created': 0,
            'updated': 0,
            'parsing_issues': 0,
            'saved': 0,
            'failed': 0,
            'errors': []
        }

        with open(filepath, 'r', encoding='utf-8', errors='replace') as f:
            reader = csv.DictReader(f)
            for row_num, row in enumerate(reader, start=2):
                stats['read'] += 1
                loc_id = str(row.get('location_id', '')).strip()
                org_id = str(row.get('org_id', '')).strip()
                name = str(row.get('location_name', row.get('name', ''))).strip()

                if not loc_id:
                    stats['parsing_issues'] += 1
                    self.stdout.write(self.style.WARNING(
                        f"  [WARNING] {filepath.name} row {row_num}: Missing location_id"
                    ))

                try:
                    with transaction.atomic():
                        loc, created = Location.objects.update_or_create(
                            location_id=loc_id,
                            defaults={
                                'org_id': org_id,
                                'name': name or loc_id,
                            }
                        )
                        if created:
                            stats['created'] += 1
                        else:
                            stats['updated'] += 1
                        stats['saved'] += 1
                except Exception as e:
                    stats['failed'] += 1
                    err_msg = f"{filepath.name} row {row_num} (loc_id={loc_id}): {str(e)}"
                    stats['errors'].append(err_msg)
                    self.stdout.write(self.style.ERROR(f"  [ERROR] Failed to save location: {err_msg}"))

        return stats

    def import_system_a(self, filepath: Path, locations_cache: Dict[str, Location]) -> Dict[str, Any]:
        self.stdout.write(f"\nImporting System A Records from: {filepath.name}...")
        stats = {
            'read': 0,
            'created': 0,
            'updated': 0,
            'parsing_issues': 0,
            'saved': 0,
            'failed': 0,
            'errors': []
        }

        with open(filepath, 'r', encoding='utf-8', errors='replace') as f:
            reader = csv.DictReader(f)
            for row_num, row in enumerate(reader, start=2):
                stats['read'] += 1
                record_id = str(row.get('record_id', '')).strip()
                location_raw = str(row.get('location_id', '')).strip()
                event_date_raw = str(row.get('event_date', '')).strip()
                category_code = str(row.get('category_code', '')).strip()
                actor_id_raw = str(row.get('actor_id', '')).strip()
                actor_id = actor_id_raw if actor_id_raw else None
                base_value_raw = str(row.get('base_value', '')).strip()
                adjustment_raw = str(row.get('adjustment', '')).strip()
                total_value_raw = str(row.get('total_value', '')).strip()
                state = str(row.get('state', '')).strip()

                has_parsing_issue = False

                # Resolve Location ForeignKey
                location_obj = locations_cache.get(location_raw)
                if location_raw and not location_obj:
                    # Attempt refresh from DB just in case
                    location_obj = Location.objects.filter(location_id=location_raw).first()
                    if location_obj:
                        locations_cache[location_raw] = location_obj
                    else:
                        has_parsing_issue = True
                        self.stdout.write(self.style.WARNING(
                            f"  [PARSING ISSUE] {filepath.name} row {row_num}: Unresolved location '{location_raw}' for record '{record_id}'"
                        ))

                # Parse Event Date
                event_date = parse_date(event_date_raw)
                if event_date_raw and event_date is None:
                    has_parsing_issue = True
                    self.stdout.write(self.style.WARNING(
                        f"  [PARSING ISSUE] {filepath.name} row {row_num}: Unparseable event_date '{event_date_raw}' for record '{record_id}'"
                    ))

                # Parse Monetary Decimals
                base_val = parse_decimal(base_value_raw)
                if base_value_raw and base_val is None:
                    has_parsing_issue = True

                adj_val = parse_decimal(adjustment_raw)
                if adjustment_raw and adj_val is None:
                    has_parsing_issue = True

                tot_val = parse_decimal(total_value_raw)
                if total_value_raw and tot_val is None:
                    has_parsing_issue = True

                if has_parsing_issue:
                    stats['parsing_issues'] += 1

                try:
                    with transaction.atomic():
                        rec, created = SystemARecord.objects.update_or_create(
                            record_id=record_id,
                            defaults={
                                'location': location_obj,
                                'location_raw': location_raw,
                                'event_date': event_date,
                                'event_date_raw': event_date_raw,
                                'category_code': category_code,
                                'actor_id': actor_id,
                                'base_value_raw': base_value_raw,
                                'base_value': base_val,
                                'adjustment_raw': adjustment_raw,
                                'adjustment': adj_val,
                                'total_value_raw': total_value_raw,
                                'total_value': tot_val,
                                'state': state,
                            }
                        )
                        if created:
                            stats['created'] += 1
                        else:
                            stats['updated'] += 1
                        stats['saved'] += 1
                except Exception as e:
                    stats['failed'] += 1
                    err_msg = f"{filepath.name} row {row_num} (record_id={record_id}): {str(e)}"
                    stats['errors'].append(err_msg)
                    self.stdout.write(self.style.ERROR(f"  [ERROR] Failed to save SystemARecord: {err_msg}"))

        return stats

    def import_system_b(self, filepath: Path, locations_cache: Dict[str, Location]) -> Dict[str, Any]:
        self.stdout.write(f"\nImporting System B Entries from: {filepath.name}...")
        stats = {
            'read': 0,
            'created': 0,
            'updated': 0,
            'parsing_issues': 0,
            'saved': 0,
            'failed': 0,
            'errors': []
        }

        with open(filepath, 'r', encoding='utf-8', errors='replace') as f:
            reader = csv.DictReader(f)
            for row_num, row in enumerate(reader, start=2):
                stats['read'] += 1
                entry_id = str(row.get('entry_id', '')).strip()
                # Preserve original verbatim raw reference string
                record_ref_raw = str(row.get('record_ref', ''))
                # Normalize reference (e.g., ' REC - 1070 ' -> 'REC-1070')
                record_ref = normalize_record_ref(record_ref_raw)

                location_raw = str(row.get('location_id', '')).strip()
                recorded_on_raw = str(row.get('recorded_on', '')).strip()
                value_raw = str(row.get('value', '')).strip()
                label = str(row.get('label', '')).strip()

                has_parsing_issue = False

                # Resolve Location ForeignKey
                location_obj = locations_cache.get(location_raw)
                if location_raw and not location_obj:
                    location_obj = Location.objects.filter(location_id=location_raw).first()
                    if location_obj:
                        locations_cache[location_raw] = location_obj
                    else:
                        has_parsing_issue = True
                        self.stdout.write(self.style.WARNING(
                            f"  [PARSING ISSUE] {filepath.name} row {row_num}: Unresolved location '{location_raw}' for entry '{entry_id}'"
                        ))

                # Parse Recorded On Date
                recorded_on = parse_date(recorded_on_raw)
                if recorded_on_raw and recorded_on is None:
                    has_parsing_issue = True
                    self.stdout.write(self.style.WARNING(
                        f"  [PARSING ISSUE] {filepath.name} row {row_num}: Unparseable recorded_on '{recorded_on_raw}' for entry '{entry_id}'"
                    ))

                # Parse Decimal (supports Indian/standard comma formatting, empty -> None)
                parsed_val = parse_decimal(value_raw)
                # If raw value string was provided but couldn't be parsed, or if empty
                if value_raw == "" or (value_raw and parsed_val is None):
                    has_parsing_issue = True

                if has_parsing_issue:
                    stats['parsing_issues'] += 1

                try:
                    with transaction.atomic():
                        entry, created = SystemBEntry.objects.update_or_create(
                            entry_id=entry_id,
                            defaults={
                                'record_ref_raw': record_ref_raw,
                                'record_ref': record_ref,
                                'location': location_obj,
                                'location_raw': location_raw,
                                'recorded_on': recorded_on,
                                'recorded_on_raw': recorded_on_raw,
                                'value_raw': value_raw,
                                'value': parsed_val,
                                'label': label,
                            }
                        )
                        if created:
                            stats['created'] += 1
                        else:
                            stats['updated'] += 1
                        stats['saved'] += 1
                except Exception as e:
                    stats['failed'] += 1
                    err_msg = f"{filepath.name} row {row_num} (entry_id={entry_id}): {str(e)}"
                    stats['errors'].append(err_msg)
                    self.stdout.write(self.style.ERROR(f"  [ERROR] Failed to save SystemBEntry: {err_msg}"))

        return stats

    def print_summary(self, stats: Dict[str, Dict[str, Any]]) -> None:
        self.stdout.write("\n" + "=" * 60)
        self.stdout.write(self.style.SUCCESS("DealerOS CSV Import Summary"))
        self.stdout.write("=" * 60)

        total_read = 0
        total_created = 0
        total_updated = 0
        total_issues = 0
        total_saved = 0
        total_failed = 0

        for category, s in stats.items():
            self.stdout.write(f"\nFile: {category}")
            self.stdout.write(f"  - Rows read:                 {s['read']}")
            self.stdout.write(f"  - Rows created:              {s['created']}")
            self.stdout.write(f"  - Rows updated:              {s['updated']}")
            self.stdout.write(f"  - Rows with parsing issues:  {s['parsing_issues']}")
            self.stdout.write(f"  - Rows successfully saved:   {s['saved']}")
            if s['failed'] > 0:
                self.stdout.write(self.style.ERROR(f"  - Rows failed (database error): {s['failed']}"))

            total_read += s['read']
            total_created += s['created']
            total_updated += s['updated']
            total_issues += s['parsing_issues']
            total_saved += s['saved']
            total_failed += s['failed']

        self.stdout.write("\n" + "-" * 60)
        self.stdout.write("Total Aggregated Statistics:")
        self.stdout.write(f"  - Total rows read:                {total_read}")
        self.stdout.write(f"  - Total records created:          {total_created}")
        self.stdout.write(f"  - Total records updated:          {total_updated}")
        self.stdout.write(f"  - Total rows with parsing issues: {total_issues}")
        self.stdout.write(f"  - Total records saved:            {total_saved}")
        if total_failed > 0:
            self.stdout.write(self.style.ERROR(f"  - Total records failed to save:   {total_failed}"))
        self.stdout.write("=" * 60 + "\n")
