from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response


class CustomPageNumberPagination(PageNumberPagination):
    page_size_query_param = "page_size"

    def get_paginated_response(self, data):
        page_size = self.get_page_size(self.request)
        current_page = self.page.number
        start_item = (current_page - 1) * page_size + 1
        end_item = min(start_item + page_size - 1, self.page.paginator.count)

        return Response(
            {
                "count": self.page.paginator.count,
                "next": self.get_next_link(),
                "previous": self.get_previous_link(),
                "page_size": page_size,
                "total_pages": self.page.paginator.num_pages,
                "current_page": current_page,
                "item_range": f"{start_item}-{end_item}",
                "results": data,
            }
        )
