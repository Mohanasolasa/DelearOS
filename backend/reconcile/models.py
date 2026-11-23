from django.db import models


class Location(models.Model):
    """
    Represents a dealership physical or logical facility.
    Location is the single source of truth for organization ownership.
    """
    location_id = models.CharField(
        max_length=64,
        unique=True,
        help_text="Unique location identifier (e.g., LOC-101)"
    )
    org_id = models.CharField(
        max_length=64,
        help_text="Organization identifier that owns this facility (e.g., ORG-A)"
    )
    name = models.CharField(
        max_length=128,
        help_text="Human-readable name of the facility (e.g., Location 101)"
    )

    class Meta:
        verbose_name = "Location"
        verbose_name_plural = "Locations"
        ordering = ['location_id']

    def __str__(self):
        return f"{self.location_id} - {self.name} ({self.org_id})"


class SystemARecord(models.Model):
    """
    Represents a transaction record from System A.
    """
    record_id = models.CharField(
        max_length=64,
        unique=True,
        help_text="Unique record identifier from System A (e.g., REC-1001)"
    )
    location = models.ForeignKey(
        Location,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='system_a_records',
        help_text="Foreign key to resolved Location entity"
    )
    location_raw = models.CharField(
        max_length=64,
        null=True,
        blank=True,
        help_text="Original raw location identifier from CSV to preserve unresolved dirty rows"
    )
    event_date = models.DateField(
        null=True,
        blank=True,
        help_text="Parsed transaction/event date"
    )
    event_date_raw = models.CharField(
        max_length=64,
        null=True,
        blank=True,
        help_text="Original raw date string from CSV to preserve unparseable dirty rows"
    )
    category_code = models.CharField(
        max_length=64,
        help_text="Category code classification (e.g., CAT-02)"
    )
    actor_id = models.CharField(
        max_length=64,
        null=True,
        blank=True,
        help_text="Identifier of the actor/user associated with the event (nullable for dirty rows)"
    )
    base_value_raw = models.CharField(
        max_length=64,
        null=True,
        blank=True,
        help_text="Original raw base value string from CSV (preserves unparseable monetary values)"
    )
    base_value = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Base monetary value before adjustments"
    )
    adjustment_raw = models.CharField(
        max_length=64,
        null=True,
        blank=True,
        help_text="Original raw adjustment string from CSV (preserves unparseable monetary values)"
    )
    adjustment = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Monetary adjustment amount"
    )
    total_value_raw = models.CharField(
        max_length=64,
        null=True,
        blank=True,
        help_text="Original raw total value string from CSV (preserves unparseable monetary values)"
    )
    total_value = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Total calculated monetary value (base_value + adjustment)"
    )
    state = models.CharField(
        max_length=64,
        help_text="Transaction state (e.g., CONFIRMED, VOIDED)"
    )

    class Meta:
        verbose_name = "System A Record"
        verbose_name_plural = "System A Records"
        ordering = ['record_id']

    def __str__(self):
        return f"SystemARecord({self.record_id}, total={self.total_value}, state={self.state})"


class SystemBEntry(models.Model):
    """
    Represents an entry from external ledger System B.
    Decoupled from System A to allow independent ingestion, discrepancy detection,
    and preservation of dirty or orphaned records.
    """
    entry_id = models.CharField(
        max_length=64,
        unique=True,
        help_text="Unique entry identifier from System B (e.g., ENT/2026/4001)"
    )
    record_ref_raw = models.CharField(
        max_length=64,
        help_text="Raw, uncleaned record reference from CSV (e.g., ' REC - 1070 ')"
    )
    record_ref = models.CharField(
        max_length=64,
        null=True,
        blank=True,
        help_text="Cleaned/normalized reference to System A record (non-unique, nullable)"
    )
    location = models.ForeignKey(
        Location,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='system_b_entries',
        help_text="Foreign key to resolved Location entity"
    )
    location_raw = models.CharField(
        max_length=64,
        null=True,
        blank=True,
        help_text="Original raw location identifier from CSV to preserve unresolved dirty rows"
    )
    recorded_on = models.DateField(
        null=True,
        blank=True,
        help_text="Parsed recording/transaction date"
    )
    recorded_on_raw = models.CharField(
        max_length=64,
        null=True,
        blank=True,
        help_text="Original raw date string from CSV to preserve unparseable dirty rows"
    )
    value_raw = models.CharField(
        max_length=64,
        blank=True,
        default="",
        help_text="Original raw monetary string from CSV (e.g., '1,25,400.00' or '')"
    )
    value = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Parsed numeric monetary value (nullable to allow dirty rows without values to survive)"
    )
    label = models.CharField(
        max_length=128,
        blank=True,
        default="",
        help_text="Descriptive label or notes for the entry"
    )

    class Meta:
        verbose_name = "System B Entry"
        verbose_name_plural = "System B Entries"
        ordering = ['entry_id']

    def __str__(self):
        return f"SystemBEntry({self.entry_id}, ref={self.record_ref}, val={self.value})"
