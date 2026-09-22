"""Tree-sitter language adapter registry."""

from dataclasses import dataclass

from tree_sitter import Node, Parser
from tree_sitter_language_pack import get_parser

from reponyx.repositories.models import ImportReference, Symbol, SymbolType


@dataclass(frozen=True, slots=True)
class LanguageAdapter:
    name: str
    grammar_name: str
    symbol_nodes: dict[str, SymbolType]
    import_nodes: tuple[str, ...]
    export_nodes: tuple[str, ...]

    def parser(self) -> Parser:
        return get_parser(self.grammar_name)


ADAPTERS: dict[str, LanguageAdapter] = {
    "python": LanguageAdapter(
        "python",
        "python",
        {
            "function_definition": SymbolType.FUNCTION,
            "class_definition": SymbolType.CLASS,
            "decorator": SymbolType.DECORATOR,
        },
        ("import_statement", "import_from_statement"),
        (),
    ),
    "javascript": LanguageAdapter(
        "javascript",
        "javascript",
        {
            "function_declaration": SymbolType.FUNCTION,
            "class_declaration": SymbolType.CLASS,
            "method_definition": SymbolType.METHOD,
        },
        ("import_statement",),
        ("export_statement",),
    ),
    "typescript": LanguageAdapter(
        "typescript",
        "typescript",
        {
            "function_declaration": SymbolType.FUNCTION,
            "class_declaration": SymbolType.CLASS,
            "method_definition": SymbolType.METHOD,
            "interface_declaration": SymbolType.INTERFACE,
            "type_alias_declaration": SymbolType.TYPE,
        },
        ("import_statement",),
        ("export_statement",),
    ),
    "java": LanguageAdapter(
        "java",
        "java",
        {
            "class_declaration": SymbolType.CLASS,
            "method_declaration": SymbolType.METHOD,
            "interface_declaration": SymbolType.INTERFACE,
            "annotation": SymbolType.DECORATOR,
        },
        ("import_declaration",),
        (),
    ),
    "go": LanguageAdapter(
        "go",
        "go",
        {
            "function_declaration": SymbolType.FUNCTION,
            "method_declaration": SymbolType.METHOD,
            "type_declaration": SymbolType.TYPE,
        },
        ("import_declaration",),
        (),
    ),
    "rust": LanguageAdapter(
        "rust",
        "rust",
        {
            "function_item": SymbolType.FUNCTION,
            "struct_item": SymbolType.CLASS,
            "enum_item": SymbolType.TYPE,
            "trait_item": SymbolType.INTERFACE,
            "impl_item": SymbolType.CLASS,
        },
        ("use_declaration",),
        (),
    ),
}


def node_text(node: Node, source: bytes) -> str:
    return source[node.start_byte : node.end_byte].decode("utf-8", errors="replace")


def node_name(node: Node, source: bytes) -> str | None:
    for child in node.children:
        if child.type in {
            "identifier",
            "type_identifier",
            "property_identifier",
            "field_identifier",
            "name",
        }:
            return node_text(child, source)
    return None


def extract_tree_entities(
    repository_id: str, file_path: str, language: str, source: bytes
) -> tuple[list[Symbol], list[ImportReference]]:
    adapter = ADAPTERS[language]
    tree = adapter.parser().parse(source)
    if tree.root_node.has_error:
        raise ValueError("source contains a syntax error")
    symbols: list[Symbol] = []
    imports: list[ImportReference] = []

    def visit(node: Node, parents: tuple[str, ...] = ()) -> None:
        name = node_name(node, source)
        symbol_type = adapter.symbol_nodes.get(node.type)
        if (
            node.type in {"function_definition", "function_declaration", "function_item"}
            and parents
        ):
            symbol_type = SymbolType.METHOD
        if symbol_type and name:
            symbols.append(
                Symbol(
                    repository_id,
                    file_path,
                    name,
                    symbol_type,
                    node.start_point[0] + 1,
                    node.end_point[0] + 1,
                    language,
                    parents[-1] if parents else None,
                    node_text(node, source).splitlines()[0][:200],
                )
            )
            parents = (*parents, name)
        if node.type in adapter.import_nodes:
            imports.append(
                ImportReference(
                    file_path,
                    node_text(node, source).strip(),
                    name,
                    node.start_point[0] + 1,
                    node.end_point[0] + 1,
                    language,
                )
            )
        if node.type in adapter.export_nodes:
            imports.append(
                ImportReference(
                    file_path,
                    node_text(node, source).strip(),
                    name,
                    node.start_point[0] + 1,
                    node.end_point[0] + 1,
                    language,
                    True,
                )
            )
        for child in node.children:
            visit(child, parents)

    visit(tree.root_node)
    return symbols, imports
