from rest_framework.pagination import PageNumberPagination


class StandardPagination(PageNumberPagination):
    """Default list pagination: ``?page=N&page_size=M``, capped at 200 items."""

    page_size = 50
    page_size_query_param = "page_size"
    max_page_size = 200
