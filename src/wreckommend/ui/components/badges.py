def rating_stars(rating: int | None) -> str:
    """Star string for a 1-5 Subsonic userRating, or '' if unrated."""
    if not rating:
        return ""
    return "★" * rating + "☆" * (5 - rating)


def heart_label_kwargs(starred) -> tuple[str, str]:
    """(glyph, css classes) for a favorite/heart Label given a Subsonic
    `starred` value (an ISO timestamp string if favorited, else falsy)."""
    is_favorited = bool(starred)
    glyph = "♥" if is_favorited else "♡"
    classes = f"heart{' favorited' if is_favorited else ''}"
    return glyph, classes
