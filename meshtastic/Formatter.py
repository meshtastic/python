"""Defines the formatting of outputs using factories"""

class FormatterFactory():
    """Factory of formatters"""
    def __init__(self):
        self.formatters = {
            "json": FormatAsJson,
            "default": FormatAsText
        }

    def getFormatter(self, formatSpec: str):
        """returns the formatter for info data. If no valid formatter is found, default to text"""
        return self.formatters.get(formatSpec, self.formatters["default"])


class InfoFormatter():
    """responsible to format info data"""
    def format(self, data: dict, formatSpec: str) -> str:
        """returns formatted string according to formatSpec for info data"""
        formatter = FormatterFactory.getFormatter(formatSpec)
        return formatter.formatInfo(data)


class FormatAsJson():
    """responsible to return the data as JSON string"""
    def formatInfo(self, data: dict) -> str:
        """Info as JSON"""
        return ""


class FormatAsText():
    """responsible to print the data. No string return"""
    def formatInfo(self, data: dict) -> str:
        """Info printed"""
        return ""
