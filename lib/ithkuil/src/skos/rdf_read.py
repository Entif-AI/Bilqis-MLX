"""Read canonical N-Triples without normalizing typed literal lexical forms."""
from __future__ import annotations

from io import StringIO

from rdflib import BNode, Graph, Literal, URIRef
from rdflib.plugins.parsers.ntriples import (
    NTGraphSink, ParseError, W3CNTriplesParser, r_literal, r_nodeid, unquote, uriquote,
)

from .canonical import canonicalize
from .errors import ProfileError


class LexicalNTriplesParser(W3CNTriplesParser):
    """Keep canonical artifact blank labels and exact typed lexical forms."""

    def nodeid(self, bnode_context=None):
        if self.peek("_"):
            return BNode(self.eat(r_nodeid).group(1))
        return False

    def literal(self):
        if not self.peek('"'):
            return False
        lexical, language, datatype = self.eat(r_literal).groups()
        if language and datatype:
            raise ParseError("Literal cannot have both a language and datatype")
        datatype = URIRef(uriquote(unquote(datatype))) if datatype else None
        return Literal(unquote(lexical), lang=language or None, datatype=datatype, normalize=False)


def read_canonical_graph(payload: bytes) -> Graph:
    if not isinstance(payload, bytes):
        raise ProfileError("CANONICAL_RDF_BYTES_REQUIRED")
    graph = Graph()
    try:
        LexicalNTriplesParser(NTGraphSink(graph)).parse(StringIO(payload.decode("utf-8")))
    except (UnicodeError, ParseError, ValueError) as error:
        raise ProfileError("CANONICAL_RDF_PARSE_ERROR", type(error).__name__) from error
    if canonicalize(graph).payload != payload:
        raise ProfileError("NONCANONICAL_RDF_INPUT")
    return graph
