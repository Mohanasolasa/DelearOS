from decimal import Decimal
from typing import List, Dict, Any, Optional

from django.db.models import Q
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from reconcile.api.serializers import DisagreementSerializer
from reconcile.models import Location, SystemARecord, SystemBEntry
from reconcile.services.reconciliation import ReconciliationEngine


VALID_REASONS = {
    "MISSING_IN_B",
    "ORPHAN_IN_B",
    "DUPLICATE_IN_B",
    "VALUE_MISMATCH",
    "LOCATION_MISMATCH",
    "DATE_MISMATCH",
    "VOIDED_IN_B",
}

VALID_SORTS = {
    "record_id",
    "value_asc",
    "value_desc",
    "difference_asc",
    "difference_desc",
}


class DisagreementListView(APIView):
    """
    GET /api/disagreements/
    Returns reconciliation discrepancies for a specified organization with strict
    database-level tenant scoping and cross-tenant redaction.
    """

    def get(self, request, *args, **kwargs):
        # 1. Validate required 'org' query parameter
        org = request.query_params.get("org")
        if not org or not org.strip():
            return Response(
                {"error": "The 'org' query parameter is required."},
                status=status.HTTP_400_BAD_REQUEST
            )
        org = org.strip()

        # Check if organization exists in canonical Location entities
        if not Location.objects.filter(org_id=org).exists():
            return Response(
                {"error": f"Organization '{org}' not found."},
                status=status.HTTP_404_NOT_FOUND
            )

        # 2. Validate optional 'reason' filter parameter
        reason_filter = request.query_params.get("reason")
        if reason_filter is not None:
            reason_filter = reason_filter.strip()
            if reason_filter not in VALID_REASONS:
                return Response(
                    {
                        "error": f"Invalid reason '{reason_filter}'. Supported reasons: {', '.join(sorted(VALID_REASONS))}."
                    },
                    status=status.HTTP_400_BAD_REQUEST
                )

        # 3. Validate optional 'sort' parameter
        sort_param = request.query_params.get("sort")
        if sort_param is not None:
            sort_param = sort_param.strip()
            if sort_param not in VALID_SORTS:
                return Response(
                    {
                        "error": f"Invalid sort parameter '{sort_param}'. Supported sorting: {', '.join(sorted(VALID_SORTS))}."
                    },
                    status=status.HTTP_400_BAD_REQUEST
                )

        # 4. Strict Database-Level Tenant Scoping
        # Rule A: Query System A records belonging to the selected organization
        scoped_a = list(
            SystemARecord.objects.filter(
                location__org_id=org
            ).select_related("location")
        )
        scoped_a_ids = [a.record_id for a in scoped_a]

        # Rule B & C: Query System B entries:
        # - referencing this organization's System A records (regardless of B location, to detect cross-loc mismatches); OR
        # - genuine orphans (not referencing any existing System A record) belonging to this organization's location.
        all_system_a_ids = SystemARecord.objects.values_list("record_id", flat=True)

        scoped_b_qs = SystemBEntry.objects.filter(
            Q(record_ref__in=scoped_a_ids) |
            (
                (Q(record_ref__isnull=True) | ~Q(record_ref__in=all_system_a_ids)) &
                Q(location__org_id=org)
            )
        ).select_related("location").distinct()
        scoped_b = list(scoped_b_qs)

        # 5. Run Reconciliation Engine on Tenant-Scoped Records
        engine = ReconciliationEngine(
            system_a_records=scoped_a,
            system_b_entries=scoped_b
        )
        disagreements = engine.reconcile()

        # 6. Apply Cross-Tenant Data Redaction
        org_location_ids = set(
            Location.objects.filter(org_id=org).values_list("location_id", flat=True)
        )

        redacted_results: List[Dict[str, Any]] = []
        for d in disagreements:
            b_loc = d.system_b_location
            # If the System B location belongs to a foreign organization, redact it to null
            if b_loc and b_loc not in org_location_ids:
                b_loc_serialized = None
                explanation = (
                    f"Location mismatch on record {d.record_id}: System A location is "
                    f"{d.system_a_location}, but System B entry {d.system_b_entry_ids[0] if d.system_b_entry_ids else ''} "
                    f"has a location outside this organization."
                )
            else:
                b_loc_serialized = b_loc
                explanation = d.explanation

            redacted_results.append({
                "reason": d.reason,
                "record_id": d.record_id,
                "system_a_location": d.system_a_location,
                "system_b_location": b_loc_serialized,
                "system_a_date": d.system_a_date,
                "system_b_date": d.system_b_date,
                "system_a_total_value": d.system_a_total_value,
                "system_b_value": d.system_b_value,
                "difference": d.difference,
                "system_b_entry_ids": d.system_b_entry_ids,
                "explanation": explanation,
            })

        # 7. Apply Optional Reason Filter
        if reason_filter:
            redacted_results = [
                d for d in redacted_results if d["reason"] == reason_filter
            ]

        # 8. Apply Optional Deterministic Sorting
        if sort_param == "record_id":
            redacted_results.sort(
                key=lambda d: (d["record_id"] is None, d["record_id"] or "")
            )
        elif sort_param == "value_asc":
            redacted_results.sort(
                key=lambda d: (
                    self._get_sort_value(d) is None,
                    self._get_sort_value(d) if self._get_sort_value(d) is not None else Decimal(0),
                    d["record_id"] or ""
                )
            )
        elif sort_param == "value_desc":
            redacted_results.sort(
                key=lambda d: (
                    self._get_sort_value(d) is None,
                    -(self._get_sort_value(d)) if self._get_sort_value(d) is not None else Decimal(0),
                    d["record_id"] or ""
                )
            )
        elif sort_param == "difference_asc":
            redacted_results.sort(
                key=lambda d: (
                    d["difference"] is None,
                    d["difference"] if d["difference"] is not None else Decimal(0),
                    d["record_id"] or ""
                )
            )
        elif sort_param == "difference_desc":
            redacted_results.sort(
                key=lambda d: (
                    d["difference"] is None,
                    -(d["difference"]) if d["difference"] is not None else Decimal(0),
                    d["record_id"] or ""
                )
            )

        # 9. Serialize Response
        serializer = DisagreementSerializer(redacted_results, many=True)
        return Response({
            "organization": org,
            "count": len(serializer.data),
            "results": serializer.data
        }, status=status.HTTP_200_OK)

    @staticmethod
    def _get_sort_value(d: Dict[str, Any]) -> Optional[Decimal]:
        """Returns the primary monetary value for sorting (System A total or orphan System B value)."""
        if d["system_a_total_value"] is not None:
            return d["system_a_total_value"]
        return d["system_b_value"]
