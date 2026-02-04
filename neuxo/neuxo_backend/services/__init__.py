from drf_spectacular.utils import OpenApiParameter, OpenApiExample

PARAMETERS = [
    OpenApiParameter(
        name="start_date",
        required=False,
        type=str,
        examples=[OpenApiExample("2024-1-1 00:00:00", value="2024-1-1 00:00:00")],
    ),
    OpenApiParameter(
        name="end_date",
        required=False,
        type=str,
        examples=[OpenApiExample("2024-12-31 00:00:00", value="2024-12-31 00:00:00")],
    ),
    OpenApiParameter(
        name="sortByVal",
        description="Attribute to order the results by (total_sale by default)",
        required=False,
        type=str,
        enum=[],
    ),
    OpenApiParameter(
        name="orderByVal",
        description="Direction in which to order the results by (ASC by default)",
        required=False,
        type=str,
        enum=["ASC", "DESC"],
    ),
    OpenApiParameter(
        name="page", required=False, type=int, examples=[OpenApiExample("1", value="1")]
    ),
    OpenApiParameter(
        name="limit",
        required=False,
        type=int,
        examples=[OpenApiExample("10", value="10")],
    ),
    OpenApiParameter(
        name="search_key",
        description="search_key",
        required=False,
        type=str,
        examples=[OpenApiExample("10", value="10")],
    ),
    OpenApiParameter(
        name="count_trigger",
        description="count_trigger",
        required=False,
        type=int,
        enum=[1, 2, 3, 4],
    ),
    OpenApiParameter(
        name="event_parent",
        description="event_parents",
        required=False,
        type=str,
        enum=[],
    ),
    OpenApiParameter(
        name="country", description="locations", required=False, type=str, enum=[]
    ),
]
