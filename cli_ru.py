import argparse
import sys


class RussianHelpFormatter(argparse.HelpFormatter):
    def _format_usage(self, usage, actions, groups, prefix):
        return super()._format_usage(
            usage=usage,
            actions=actions,
            groups=groups,
            prefix=prefix or "Использование: ",
        )


class RussianArgumentParser(argparse.ArgumentParser):
    def error(self, message: str) -> None:
        translations = {
            "argument": "аргумент",
            "unrecognized arguments": "неизвестные аргументы",
            "the following arguments are required": "не указаны обязательные аргументы",
            "invalid float value": "некорректное число",
            "expected one argument": "ожидался один аргумент",
        }
        for english, russian in translations.items():
            message = message.replace(english, russian)

        self.print_usage(sys.stderr)
        self.exit(2, f"{self.prog}: ошибка: {message}\n")


def create_russian_parser(description: str) -> RussianArgumentParser:
    parser = RussianArgumentParser(
        description=description,
        formatter_class=RussianHelpFormatter,
    )
    parser._positionals.title = "позиционные аргументы"
    parser._optionals.title = "параметры"
    parser._optionals._group_actions[0].help = "показать эту справку и выйти"
    return parser
