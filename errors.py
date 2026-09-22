class ConfigurationError(RuntimeError):
    pass


class LlmApiError(RuntimeError):
    def __init__(self, message: str, *, status_code: int | None = None, details: str | None = None) -> None:
        self.status_code = status_code
        self.details = details
        super().__init__(message)


def format_error(error: BaseException) -> str:
    if isinstance(error, BaseExceptionGroup):
        messages = [format_error(item) for item in error.exceptions]
        messages = [message for message in messages if message]
        return "; ".join(messages) or str(error)

    cause = error.__cause__ or error.__context__
    if cause is not None:
        cause_message = format_error(cause)
        if cause_message and cause_message != str(error):
            return f"{error}: {cause_message}"

    return str(error) or error.__class__.__name__
