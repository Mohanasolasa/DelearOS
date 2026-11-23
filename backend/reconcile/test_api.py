from decimal import Decimal
from datetime import date
import pytest
from rest_framework import status
from rest_framework.test import APIClient

from reconcile.models import Location, SystemARecord, SystemBEntry


@pytest.mark.django_db
class TestDisagreementAPI:
    @pytest.fixture(autouse=True)
    def setup_data(self):
        self.client = APIClient()

        # Create locations for two distinct organizations
        self.loc_a1 = Location.objects.create(location_id="LOC-101", org_id="ORG-A", name="Location 101")
        self.loc_a2 = Location.objects.create(location_id="LOC-102", org_id="ORG-A", name="Location 102")
        self.loc_b1 = Location.objects.create(location_id="LOC-201", org_id="ORG-B", name="Location 201")
        self.loc_b2 = Location.objects.create(location_id="LOC-202", org_id="ORG-B", name="Location 202")

        # 1. ORG-A: Value mismatch
        self.rec_a1 = SystemARecord.objects.create(
            record_id="REC-A-01",
            location=self.loc_a1,
            event_date=date(2026, 4, 1),
            category_code="CAT-01",
            total_value=Decimal("1000.00"),
            state="CONFIRMED"
        )
        self.entry_a1 = SystemBEntry.objects.create(
            entry_id="ENT-A-01",
            record_ref="REC-A-01",
            record_ref_raw="REC-A-01",
            location=self.loc_a1,
            recorded_on=date(2026, 4, 1),
            value=Decimal("800.00"),
            value_raw="800.00"
        )

        # 2. ORG-A: Missing in B
        self.rec_a2 = SystemARecord.objects.create(
            record_id="REC-A-02",
            location=self.loc_a1,
            event_date=date(2026, 4, 2),
            category_code="CAT-01",
            total_value=Decimal("500.00"),
            state="CONFIRMED"
        )

        # 3. Cross-Tenant record: REC-1077 belongs to ORG-A, but B entry has location in ORG-B
        self.rec_cross = SystemARecord.objects.create(
            record_id="REC-1077",
            location=self.loc_a2,  # ORG-A
            event_date=date(2026, 3, 19),
            category_code="CAT-04",
            total_value=Decimal("83361.40"),
            state="CONFIRMED"
        )
        self.entry_cross = SystemBEntry.objects.create(
            entry_id="ENT-4077",
            record_ref="REC-1077",
            record_ref_raw="REC-1077",
            location=self.loc_b1,  # ORG-B!
            recorded_on=date(2026, 3, 19),
            value=Decimal("83361.40"),
            value_raw="83361.40"
        )

        # 4. ORG-A: Orphan B entry (B location belongs to ORG-A, ref does not exist in System A)
        self.orphan_a = SystemBEntry.objects.create(
            entry_id="ENT-ORPHAN-A",
            record_ref="REC-NONEXISTENT-A",
            record_ref_raw="REC-NONEXISTENT-A",
            location=self.loc_a2,  # ORG-A
            recorded_on=date(2026, 3, 18),
            value=Decimal("41250.00"),
            value_raw="41250.00"
        )

        # 5. ORG-B: Value mismatch with blank value (None)
        self.rec_b1 = SystemARecord.objects.create(
            record_id="REC-B-01",
            location=self.loc_b2,  # ORG-B
            event_date=date(2026, 3, 20),
            category_code="CAT-03",
            total_value=Decimal("160405.85"),
            state="CONFIRMED"
        )
        self.entry_b1 = SystemBEntry.objects.create(
            entry_id="ENT-B-01",
            record_ref="REC-B-01",
            record_ref_raw="REC-B-01",
            location=self.loc_b2,
            recorded_on=date(2026, 3, 20),
            value=None,  # Blank monetary value!
            value_raw=""
        )

        # 6. ORG-B: VOIDED System A record with entry in B
        self.rec_b_void = SystemARecord.objects.create(
            record_id="REC-1019",
            location=self.loc_b2,
            event_date=date(2026, 4, 5),
            category_code="CAT-07",
            total_value=Decimal("57092.35"),
            state="VOIDED"
        )
        self.entry_b_void = SystemBEntry.objects.create(
            entry_id="ENT-4019",
            record_ref="REC-1019",
            record_ref_raw="REC-1019",
            location=self.loc_b2,
            recorded_on=date(2026, 4, 5),
            value=Decimal("57092.35"),
            value_raw="57092.35"
        )

    def test_successful_org_a_request(self):
        """1. Successful request for ORG-A returns HTTP 200 and expected schema."""
        response = self.client.get("/api/disagreements/?org=ORG-A")
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["organization"] == "ORG-A"
        assert isinstance(data["count"], int)
        assert data["count"] == len(data["results"])
        assert data["count"] > 0

    def test_successful_org_b_request(self):
        """2. Successful request for ORG-B returns HTTP 200 and expected schema."""
        response = self.client.get("/api/disagreements/?org=ORG-B")
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["organization"] == "ORG-B"
        assert isinstance(data["count"], int)
        assert data["count"] == len(data["results"])
        assert data["count"] > 0

    def test_missing_org_parameter(self):
        """3. Missing 'org' query parameter returns HTTP 400 Bad Request."""
        response = self.client.get("/api/disagreements/")
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        data = response.json()
        assert "org" in data["error"].lower()

    def test_unknown_organization(self):
        """4. Unknown organization returns HTTP 404 Not Found."""
        response = self.client.get("/api/disagreements/?org=UNKNOWN-ORG")
        assert response.status_code == status.HTTP_404_NOT_FOUND
        data = response.json()
        assert "not found" in data["error"].lower()

    def test_valid_reason_filter(self):
        """5. Valid reason filter returns only disagreements matching that reason."""
        response = self.client.get("/api/disagreements/?org=ORG-A&reason=VALUE_MISMATCH")
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        for r in data["results"]:
            assert r["reason"] == "VALUE_MISMATCH"

    def test_invalid_reason_filter(self):
        """6. Invalid reason filter returns HTTP 400 Bad Request."""
        response = self.client.get("/api/disagreements/?org=ORG-A&reason=INVALID_REASON")
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        data = response.json()
        assert "invalid reason" in data["error"].lower()

    def test_valid_sorting(self):
        """7. Valid sorting parameters order results deterministically."""
        # sort=record_id
        res_rec = self.client.get("/api/disagreements/?org=ORG-A&sort=record_id")
        assert res_rec.status_code == status.HTTP_200_OK
        ids = [r["record_id"] for r in res_rec.json()["results"] if r["record_id"]]
        assert ids == sorted(ids)

        # sort=value_asc
        res_asc = self.client.get("/api/disagreements/?org=ORG-A&sort=value_asc")
        assert res_asc.status_code == status.HTTP_200_OK

        # sort=value_desc
        res_desc = self.client.get("/api/disagreements/?org=ORG-A&sort=value_desc")
        assert res_desc.status_code == status.HTTP_200_OK

        # sort=difference_asc
        res_diff_asc = self.client.get("/api/disagreements/?org=ORG-A&sort=difference_asc")
        assert res_diff_asc.status_code == status.HTTP_200_OK

        # sort=difference_desc
        res_diff_desc = self.client.get("/api/disagreements/?org=ORG-A&sort=difference_desc")
        assert res_diff_desc.status_code == status.HTTP_200_OK

    def test_invalid_sorting(self):
        """8. Invalid sort parameter returns HTTP 400 Bad Request."""
        response = self.client.get("/api/disagreements/?org=ORG-A&sort=malicious_field")
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        data = response.json()
        assert "invalid sort" in data["error"].lower()

    def test_org_a_cannot_see_org_b_records(self):
        """9. ORG-A cannot see ORG-B's ordinary records."""
        response = self.client.get("/api/disagreements/?org=ORG-A")
        assert response.status_code == status.HTTP_200_OK
        record_ids = {r["record_id"] for r in response.json()["results"]}
        assert "REC-B-01" not in record_ids
        assert "REC-1019" not in record_ids

    def test_org_b_cannot_see_org_a_records(self):
        """10. ORG-B cannot see ORG-A's ordinary records."""
        response = self.client.get("/api/disagreements/?org=ORG-B")
        assert response.status_code == status.HTTP_200_OK
        record_ids = {r["record_id"] for r in response.json()["results"]}
        assert "REC-A-01" not in record_ids
        assert "REC-A-02" not in record_ids

    def test_rec_1077_visible_to_org_a_with_b_location_redacted(self):
        """11. REC-1077 is visible to ORG-A with System B location redacted (null) and no foreign org leaked."""
        response = self.client.get("/api/disagreements/?org=ORG-A")
        assert response.status_code == status.HTTP_200_OK
        results = response.json()["results"]
        cross_disagreements = [r for r in results if r["record_id"] == "REC-1077"]

        assert len(cross_disagreements) == 1
        d = cross_disagreements[0]
        assert d["reason"] == "LOCATION_MISMATCH"
        assert d["system_a_location"] == "LOC-102"
        # System B location must be REDACTED to null because LOC-201 belongs to ORG-B
        assert d["system_b_location"] is None
        # Explanation must not leak the foreign location code or organization
        assert "LOC-201" not in d["explanation"]
        assert "ORG-B" not in d["explanation"]

    def test_rec_1077_not_visible_to_org_b(self):
        """12. REC-1077 is NOT visible to ORG-B even though its System B entry has an ORG-B location."""
        response = self.client.get("/api/disagreements/?org=ORG-B")
        assert response.status_code == status.HTTP_200_OK
        record_ids = {r["record_id"] for r in response.json()["results"]}
        assert "REC-1077" not in record_ids

    def test_orphan_b_entries_visible_only_to_owning_b_location_org(self):
        """13. Orphan B entries are visible only to the organization owning their B location."""
        # ENT-ORPHAN-A location is LOC-102 (ORG-A)
        res_a = self.client.get("/api/disagreements/?org=ORG-A")
        orphan_a_results = [r for r in res_a.json()["results"] if r["record_id"] == "REC-NONEXISTENT-A"]
        assert len(orphan_a_results) == 1
        assert orphan_a_results[0]["reason"] == "ORPHAN_IN_B"

        # Must NOT appear for ORG-B
        res_b = self.client.get("/api/disagreements/?org=ORG-B")
        orphan_b_results = [r for r in res_b.json()["results"] if r["record_id"] == "REC-NONEXISTENT-A"]
        assert len(orphan_b_results) == 0

    def test_b_entry_referencing_other_org_not_exposed_to_b_location_org(self):
        """14. System B entry referencing another org's record is not exposed to the B location's org."""
        response = self.client.get("/api/disagreements/?org=ORG-B")
        entry_ids = []
        for r in response.json()["results"]:
            entry_ids.extend(r["system_b_entry_ids"])
        # ENT-4077 has location in ORG-B, but references REC-1077 in ORG-A -> MUST NOT leak to ORG-B
        assert "ENT-4077" not in entry_ids

    def test_blank_monetary_values_remain_null(self):
        """15. Blank monetary values remain null in JSON output, never converted to 0 or 0.00."""
        response = self.client.get("/api/disagreements/?org=ORG-B")
        results = response.json()["results"]
        b_val_missing = [r for r in results if r["record_id"] == "REC-B-01"]
        assert len(b_val_missing) == 1
        d = b_val_missing[0]
        assert d["reason"] == "VALUE_MISMATCH"
        assert d["system_b_value"] is None
        assert d["difference"] is None

    def test_decimal_values_remain_precise_strings_in_json(self):
        """16. Decimal values remain exact decimal strings in JSON (not floats)."""
        response = self.client.get("/api/disagreements/?org=ORG-A")
        results = response.json()["results"]
        d = next(r for r in results if r["record_id"] == "REC-A-01")
        assert isinstance(d["system_a_total_value"], str)
        assert d["system_a_total_value"] == "1000.00"
        assert isinstance(d["system_b_value"], str)
        assert d["system_b_value"] == "800.00"
        assert isinstance(d["difference"], str)
        assert d["difference"] == "-200.00"

    def test_voided_in_b_correctly_represented(self):
        """17. VOIDED_IN_B is correctly returned for voided records with entries in System B."""
        response = self.client.get("/api/disagreements/?org=ORG-B")
        results = response.json()["results"]
        void_results = [r for r in results if r["record_id"] == "REC-1019"]
        assert len(void_results) == 1
        d = void_results[0]
        assert d["reason"] == "VOIDED_IN_B"
        assert d["system_b_entry_ids"] == ["ENT-4019"]
        assert d["system_a_total_value"] == "57092.35"
