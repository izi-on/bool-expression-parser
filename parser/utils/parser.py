from typing import List
from ..expressions.models import Expression
from ..types.expressions import Token, Combinator, Result


def is_type(expression: Expression):
    def takes(tokens: List[Token]):
        return Result(
            success=isinstance(expression, tokens[0][1]),
            value=[tokens[0]],
            rest=tokens[1:],
        )

    return takes


def either(combinators: List[Combinator]):
    def takes(tokens: List[Token]):
        for combinator in combinators:
            result = combinator(tokens)
            if result.success:
                return result
        return Result(success=False)  # type: ignore

    return takes


def sequence(combinators: List[Combinator]):
    def takes(tokens: List[Token]):
        rest = tokens
        value: List[Token] = []
        for combinator in combinators:
            result = combinator(tokens)
            if result.success:
                rest = result.rest
                value.append(result.value)  # type: ignore
            else:
                return Result(success=False)  # type: ignore
        return Result(success=True, value=value, rest=rest)

    return takes
