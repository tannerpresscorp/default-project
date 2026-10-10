from rest_framework.pagination import PageNumberPagination


class StandardPagination(PageNumberPagination):
    """Page-number pagination with a client-overridable `page_size`."""

    page_size_query_param = 'page_size'
    max_page_size = 100