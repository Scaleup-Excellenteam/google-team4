from __future__ import annotations
from dataclasses import dataclass
from typing import Optional, Set, Iterable, Tuple
from array import array
import bisect

@dataclass
class _Node:
    key: str
    values: Set[int]
    left: Optional["_Node"] = None
    right: Optional["_Node"] = None

class BST:
    """
    Binary Search Tree keyed by 3-gram strings.
    Build-time: pointer nodes with set[int] postings (insert/get).
    Frozen (cache) form: compact arrays (sorted keys + array('I') postings) for fast pickle load.
    Also exposes iter_items() for exporting to custom formats (e.g., ACX).
    """
    def __init__(self) -> None:
        self._root: Optional[_Node] = None
        self._frozen: bool = False
        self._keys: list[str] | None = None
        self._postings: list[array] | None = None  # array('I')

    # -------- Build-time API --------
    def insert(self, key: str, sentence_id: int) -> None:
        if self._frozen:
            raise RuntimeError("BST is frozen; cannot insert")
        def _ins(node: Optional[_Node], key: str, sid: int) -> _Node:
            if node is None:
                return _Node(key=key, values={sid})
            if key == node.key:
                node.values.add(sid)
            elif key < node.key:
                node.left = _ins(node.left, key, sid)
            else:
                node.right = _ins(node.right, key, sid)
            return node
        self._root = _ins(self._root, key, sentence_id)

    def get(self, key: str) -> Set[int]:
        if self._frozen:
            assert self._keys is not None and self._postings is not None
            i = bisect.bisect_left(self._keys, key)
            if i != len(self._keys) and self._keys[i] == key:
                return set(self._postings[i])
            return set()
        node = self._root
        while node is not None:
            if key == node.key:
                return node.values
            node = node.left if key < node.key else node.right
        return set()

    # -------- Freeze/Export --------
    def freeze(self) -> None:
        if self._frozen:
            return
        items: list[tuple[str, Set[int]]] = []
        def _inorder(n: Optional[_Node]) -> None:
            if n is None: return
            _inorder(n.left)
            items.append((n.key, n.values))
            _inorder(n.right)
        _inorder(self._root)
        items.sort(key=lambda kv: kv[0])
        self._keys = [k for k, _ in items]
        self._postings = [array("I", sorted(v)) for _, v in items]
        self._root = None
        self._frozen = True

    @classmethod
    def from_pairs(cls, pairs: Iterable[Tuple[str, Iterable[int]]]) -> "BST":
        inst = cls()
        items = sorted(((k, sorted(set(ids))) for k, ids in pairs), key=lambda kv: kv[0])
        inst._keys = [k for k, _ in items]
        inst._postings = [array("I", v) for _, v in items]
        inst._root = None
        inst._frozen = True
        return inst

    def iter_items(self) -> Iterable[Tuple[str, Iterable[int]]]:
        """Yield (key, iterable_of_ids) in sorted-key order."""
        if self._frozen:
            assert self._keys is not None and self._postings is not None
            for k, arr in zip(self._keys, self._postings):
                yield k, arr
        else:
            def _inorder(n: Optional[_Node]) -> Iterable[Tuple[str, Iterable[int]]]:
                if n is None: return
                yield from _inorder(n.left)
                yield (n.key, n.values)
                yield from _inorder(n.right)
            yield from _inorder(self._root)

    # Pickle hooks keep only compact form
    def __getstate__(self):
        if not self._frozen:
            self.freeze()
        return {"_frozen": True, "_keys": self._keys, "_postings": self._postings}

    def __setstate__(self, state):
        self._root = None
        self._frozen = bool(state.get("_frozen", False))
        self._keys = state.get("_keys")
        self._postings = state.get("_postings")
