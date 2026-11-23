from rest_framework import serializers


class DisagreementSerializer(serializers.Serializer):
    """
    Serializes a single reconciliation discrepancy.
    Ensures precise decimal string representation without floating-point conversion,
    and null preservation for unprovided/redacted values.
    """
    reason = serializers.CharField()
    record_id = serializers.CharField(allow_null=True)
    system_a_location = serializers.CharField(allow_null=True)
    system_b_location = serializers.CharField(allow_null=True)
    system_a_date = serializers.DateField(allow_null=True)
    system_b_date = serializers.DateField(allow_null=True)
    system_a_total_value = serializers.DecimalField(
        max_digits=14,
        decimal_places=2,
        coerce_to_string=True,
        allow_null=True
    )
    system_b_value = serializers.DecimalField(
        max_digits=14,
        decimal_places=2,
        coerce_to_string=True,
        allow_null=True
    )
    difference = serializers.DecimalField(
        max_digits=14,
        decimal_places=2,
        coerce_to_string=True,
        allow_null=True
    )
    system_b_entry_ids = serializers.ListField(
        child=serializers.CharField()
    )
    explanation = serializers.CharField()


class ReconciliationResponseSerializer(serializers.Serializer):
    """
    Top-level envelope for the reconciliation API response.
    """
    organization = serializers.CharField()
    count = serializers.IntegerField()
    results = DisagreementSerializer(many=True)
