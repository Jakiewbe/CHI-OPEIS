class GuiFieldError(ValueError):
    """Invalid GUI input tied to one visible field."""

    def __init__(self, field: str, message: str) -> None:
        super().__init__(message)
        self.field = field
        self.message = message


__all__ = ["GuiFieldError"]
