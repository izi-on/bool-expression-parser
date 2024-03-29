import string
from typing import Union, List, Type
from bool_parser.types.expressions import Token
from functools import partial

from bool_parser.expressions.models import (
    PARANTHESES_TO_CLASS,
    BooleanLiteral,
    NumericLiteral,
    LeftParanthesis,
    Operator,
    ReturnTypes,
    RightParanthesis,
    SymbolTableType,
)
from bool_parser.expressions.exceptions import (
    InvalidCharacter,
    InvalidExpression,
    MatchError,
    MissingLeftParanthesis,
    MissingRightParanthesis,
)
from bool_parser.expressions.models import (
    Expression,
    Identifier,
    TOKEN_TO_CLASS,
)
from bool_parser.parser_config import rules

parantheses = set(PARANTHESES_TO_CLASS.keys())
operation_symbols = set(TOKEN_TO_CLASS.keys())
variable_symbols = set(string.ascii_letters + string.digits + "_.")
boolean_literal_symbols = set("TrueFalse")
numeric_literal_symbols = set(string.digits + ".")
language = {
    *parantheses,
    *boolean_literal_symbols,
    *operation_symbols,
    *variable_symbols,
}

ParseItem = Union[Token, Expression]


def _tokenize(s: str, symbol_table: SymbolTableType) -> list[Token]:
    """
    Tokenizes the string input from the user
    """

    def _match_op_symbol(ptr: int) -> tuple[Operator, int]:
        extend = 0
        while (
            ptr + extend + 1 <= len(s)
            and s[ptr : ptr + extend + 1] in TOKEN_TO_CLASS.keys()
        ):
            extend += 1
        c = s[ptr : ptr + extend]
        return Operator(c), extend

    def _match_literal_or_var(ptr: int, allowed_symbols: set[str]):
        start = ptr
        while ptr < len(s) and s[ptr] in allowed_symbols:
            ptr += 1
        if ptr < len(s) and s[ptr] not in language:
            raise InvalidCharacter
        return start, ptr

    tokens: List[Token] = []
    s = s.replace(" ", "")  # remove whitespace
    ptr = 0
    while ptr < len(s):
        c = s[ptr]

        if c not in language:
            raise InvalidCharacter

        if c in parantheses:
            tokens.append(PARANTHESES_TO_CLASS[c]())
            ptr += 1
            continue

        if c in operation_symbols:
            operator, extend = _match_op_symbol(ptr)
            tokens.append(operator)
            ptr += extend
            continue

        # match, then check if literal
        allowed_symbols = {
            *numeric_literal_symbols,
            *boolean_literal_symbols,
            *variable_symbols,
        }
        start_ptr, end_ptr = _match_literal_or_var(ptr, allowed_symbols)
        token_str = s[start_ptr:end_ptr]
        if BooleanLiteral.allows(token_str):
            tokens.append(BooleanLiteral(token_str))
        elif NumericLiteral.allows(token_str):
            tokens.append(NumericLiteral(token_str))
        else:
            tokens.append(Identifier(token_str, symbol_table))
        ptr = end_ptr

    return tokens


def _build_ast(tokens: list[Token], symbol_table: SymbolTableType) -> Expression:
    """
    This function builds the abstract syntax tree for the boolean expression.
    """

    """
    ____________________________
    Helper Function definitions:
    """
    recurse = partial(_build_ast, symbol_table=symbol_table)

    def _get_subexpressions(tokens: list[Token]):
        sub_exps: List[tuple[int, int]] = []  # default value necessary
        stack: List[int] = []
        for i in range(len(tokens)):
            match tokens[i]:  # type: ignore
                case LeftParanthesis():
                    stack.append(i)
                case RightParanthesis():
                    try:
                        start_idx = stack.pop()
                    except IndexError:
                        raise MissingLeftParanthesis(
                            "empty stack during parsing of subexpression"
                        )
                    if len(stack) == 0:
                        sub_exps.append((start_idx, i))
        if len(stack) != 0:
            raise MissingRightParanthesis(
                "found unclosed paranthesis at the end of parsing subexpression"
            )
        return sub_exps

    def _match(
        to_parse: List[ParseItem],
        to_match: set[Expression],
    ) -> tuple[bool, int, int, Expression]:
        class TrieNode:
            def __init__(
                self,
                value: Union[ReturnTypes, Operator, None] = None,
                children: dict[Union[ReturnTypes, Operator], "TrieNode"] = {},
                is_end: bool = False,
            ):
                self.value = value
                self.children = children
                self.is_end = is_end

        def _build_trie(to_match: set[Expression]):
            root = TrieNode(children={}, is_end=False)
            for expression in to_match:
                m_list = expression.expects  # list/sequence to match
                cur_node = root
                for match_item in m_list:
                    if match_item not in cur_node.children:
                        cur_node.children[match_item] = TrieNode(match_item, {}, False)
                    cur_node = cur_node.children[match_item]
                cur_node.is_end = True
            return root

        def is_match(
            cur_idx: int, trie: TrieNode
        ) -> tuple[bool, list[Expression], Type[Expression]]:
            cur_node = trie
            targets = []
            expr_type: Type[Expression] = None  # type: ignore
            try:
                while not cur_node.is_end:
                    cur_item = to_parse[cur_idx]
                    item_matcher = (
                        cur_item.returns
                        if isinstance(cur_item, Expression)
                        else cur_item
                    )

                    if item_matcher not in cur_node.children:
                        return False, None, None  # type: ignore
                    cur_node = cur_node.children[item_matcher]
                    cur_idx += 1
                    if isinstance(cur_item, Operator):
                        expr_type = TOKEN_TO_CLASS[cur_item.operator]
                    else:
                        targets.append(cur_item)

                if not expr_type:
                    raise MatchError(
                        "could not find the expression type (was an operator provided?)"
                    )
                return True, targets, expr_type
            except IndexError:
                return False, None, None  # type: ignore

        trie = _build_trie(to_match)
        for i in range(0, len(to_parse)):
            result, targets, expr_type = is_match(i, trie)
            if result:
                expression = expr_type(targets)
                return result, i, i + len(expr_type.expects), expression

        return False, None, None, None  # type: ignore

    """
    ____________________________
    """
    to_parse: List[ParseItem] = []

    # step 1: parse all subexpressions first
    sub_exps = (
        [(-2, -1)] + _get_subexpressions(tokens) + [(len(tokens), len(tokens) + 1)]
    )
    i = -2
    for sub_exp in sub_exps:
        to_parse += tokens[i : sub_exp[0]]
        sublist = tokens[sub_exp[0] + 1 : sub_exp[1]]
        if sublist:
            to_parse += [recurse(sublist)]
        i = sub_exp[1] + 1

    # step 2: parse in order defined by parser_config
    for expressions in rules.order_of_operations:
        matched, match_idx, end_idx, expr = _match(to_parse, expressions)
        while matched:
            to_parse = to_parse[:match_idx] + [expr] + to_parse[end_idx:]
            matched, match_idx, end_idx, expr = _match(to_parse, expressions)
    if len(to_parse) != 1 or not isinstance(to_parse[0], Expression):
        raise InvalidExpression(f"At the end of parse, got: {to_parse}")

    return to_parse[0]


def _evaluate_ast(_ast: Expression) -> bool:
    return _ast.operation()


def eval_expression(input: str, symbol_table: SymbolTableType) -> bool:
    """
    Evaluates the input expression with the given symbol_table.
    Necessarily returns a boolean value.
    """
    tokens = _tokenize(input, symbol_table)
    ast = _build_ast(tokens, symbol_table)
    return _evaluate_ast(ast)
