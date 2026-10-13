"""HTTP 查询接口共用的分页参数校验。"""

from flask import Request


class PaginationError(ValueError):
    """客户端传入了不能安全用于查询的分页参数。"""


def _positive_int(request: Request, name: str, default: int, maximum: int | None = None) -> int:
    raw = request.args.get(name)
    if raw is None or raw == "":
        return default
    try:
        value = int(raw)
    except (TypeError, ValueError):
        raise PaginationError(f"{name} 必须是整数")
    if value < 1:
        raise PaginationError(f"{name} 必须是大于等于 1 的整数")
    if maximum is not None and value > maximum:
        raise PaginationError(f"{name} 不能大于 {maximum}")
    return value


def parse_page(request: Request, default_size: int = 10, max_size: int = 1000) -> tuple[int, int]:
    """解析 page/page_size，并返回 ``(page, page_size)``。"""

    return (
        _positive_int(request, "page", 1),
        _positive_int(request, "page_size", default_size, max_size),
    )


def parse_range(request: Request, default_size: int = 50, max_size: int = 1000) -> tuple[int, int]:
    """解析 page/page_size 或 offset/page_size，返回 ``(limit, offset)``。"""

    page_size = request.args.get("page_size", request.args.get("limit"))
    if page_size is None or page_size == "":
        limit = default_size
    else:
        try:
            limit = int(page_size)
        except (TypeError, ValueError):
            raise PaginationError("page_size 必须是整数")
        if limit < 1:
            raise PaginationError("page_size 必须是大于等于 1 的整数")
        if limit > max_size:
            raise PaginationError(f"page_size 不能大于 {max_size}")

    if request.args.get("offset") is not None:
        try:
            offset = int(request.args["offset"])
        except (TypeError, ValueError):
            raise PaginationError("offset 必须是整数")
        if offset < 0:
            raise PaginationError("offset 必须是大于等于 0 的整数")
    else:
        page = _positive_int(request, "page", 1)
        offset = (page - 1) * limit
    return limit, offset
