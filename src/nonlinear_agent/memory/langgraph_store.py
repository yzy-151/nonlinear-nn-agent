"""LangGraph Store adapters for the MemoryBackend port.

- Offline / tests: ``InMemoryStore`` (no external services).
- Production profile: ``PostgresMemoryBackend`` requires ``psycopg``; missing
  driver raises a clear ImportError instead of silently degrading.

Namespaces are fixed as ``(domain, dataset_hash, model_family)`` under the
``("nonlinear_agent", "memory")`` prefix, giving cross-dataset isolation.
"""

from __future__ import annotations

from dataclasses import asdict
from typing import Any

from nonlinear_agent.memory.ports import MemoryItem, MemoryKind


_PREFIX = ("nonlinear_agent", "memory")
_INDEX_NS = ("nonlinear_agent", "memory", "_index")


def _to_dict(item: MemoryItem) -> dict[str, Any]:
    data = asdict(item)
    data["kind"] = item.kind.value
    data["namespace"] = list(item.namespace)
    data["evidence_refs"] = list(item.evidence_refs)
    return data


def _from_dict(data: dict[str, Any]) -> MemoryItem:
    data = dict(data)
    data["kind"] = MemoryKind(data["kind"])
    data["namespace"] = tuple(data["namespace"])
    data["evidence_refs"] = tuple(data.get("evidence_refs") or ())
    return MemoryItem(**data)


class LangGraphMemoryBackend:
    """MemoryBackend backed by ``langgraph.store.memory.InMemoryStore``."""

    def __init__(self, store: Any | None = None):
        from langgraph.store.memory import InMemoryStore

        self._store = store if store is not None else InMemoryStore()

    # ── 内部 ──────────────────────────────────────────────
    def _ns(self, namespace: tuple[str, str, str]) -> tuple[str, ...]:
        return (*_PREFIX, *namespace)

    def _index_get(self, memory_id: str) -> tuple[str, str, str] | None:
        item = self._store.get(_INDEX_NS, memory_id)
        if item is None:
            return None
        return tuple(item.value["namespace"])  # type: ignore[return-value]

    # ── MemoryBackend ─────────────────────────────────────
    def write(self, item: MemoryItem) -> str:
        self._store.put(
            self._ns(item.namespace),
            item.memory_id,
            _to_dict(item),
            index=["kind", "dataset_hash", "run_id"],
        )
        # 侧索引：memory_id -> namespace（get() 无需调用方提供 namespace）
        self._store.put(
            _INDEX_NS,
            item.memory_id,
            {"namespace": list(item.namespace)},
        )
        return item.memory_id

    def get(self, memory_id: str) -> MemoryItem | None:
        namespace = self._index_get(memory_id)
        if namespace is None:
            return None
        raw = self._store.get(self._ns(namespace), memory_id)
        if raw is None:
            return None
        return _from_dict(raw.value)

    def query(
        self,
        namespace: tuple[str, str, str],
        kind: MemoryKind | None = None,
        top_k: int = 5,
    ) -> list[MemoryItem]:
        kwargs: dict[str, Any] = {"limit": top_k}
        if kind is not None:
            kwargs["filter"] = {"kind": kind.value}
        hits = self._store.search(self._ns(namespace), **kwargs)
        return [_from_dict(hit.value) for hit in hits]

    def invalidate(self, memory_id: str, invalidated_at: float | None = None) -> None:
        item = self.get(memory_id)
        if item is None:
            return
        replaced = MemoryItem(
            **{
                **asdict(item),
                "kind": item.kind,
                "invalidated_at": invalidated_at if invalidated_at is not None else item.invalidated_at,
            }
        )
        if replaced.invalidated_at is None:
            import time

            replaced = MemoryItem(
                **{
                    **asdict(item),
                    "kind": item.kind,
                    "invalidated_at": time.time(),
                }
            )
        self.write(replaced)

    def list_by_run(self, run_id: str) -> list[MemoryItem]:
        hits = self._store.search(
            _PREFIX, filter={"run_id": run_id}, limit=1000
        )
        return [_from_dict(hit.value) for hit in hits]

    def list_namespaces(self) -> list[tuple[str, str, str]]:
        """All (domain, dataset_hash, model_family) namespaces with data."""
        namespaces = self._store.list_namespaces(prefix=_PREFIX)
        return [
            tuple(ns[len(_PREFIX):])  # type: ignore[return-value]
            for ns in namespaces
            if len(ns) > len(_PREFIX)
            and not (len(ns) == len(_PREFIX) + 1 and ns[-1] == "_index")
        ]

    def delete_run(self, run_id: str) -> list[str]:
        removed: list[str] = []
        for item in self.list_by_run(run_id):
            namespace = self._index_get(item.memory_id)
            if namespace is not None:
                self._store.delete(self._ns(namespace), item.memory_id)
            self._store.delete(_INDEX_NS, item.memory_id)
            removed.append(item.memory_id)
        return removed

    def close(self) -> None:
        self._store = None  # type: ignore[assignment]


class PostgresMemoryBackend:
    """Production MemoryBackend backed by Postgres via ``psycopg``.

    The driver is an optional dependency: constructing this backend without
    psycopg installed raises a clear ImportError (no silent degradation).
    """

    def __init__(self, connection_string: str):
        try:
            import psycopg  # noqa: F401
        except ImportError as exc:
            raise ImportError(
                "PostgresMemoryBackend requires psycopg (pip install psycopg[binary]). "
                "Offline tests and local runs should use LangGraphMemoryBackend "
                "(InMemoryStore) instead."
            ) from exc
        self._connection_string = connection_string
        self._conn = psycopg.connect(connection_string)
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS agent_memory (
                memory_id TEXT PRIMARY KEY,
                kind TEXT NOT NULL,
                namespace TEXT NOT NULL,
                payload JSONB NOT NULL,
                dataset_hash TEXT NOT NULL,
                run_id TEXT NOT NULL,
                created_at DOUBLE PRECISION NOT NULL
            )
            """
        )
        self._conn.commit()

    def _execute(self, sql: str, params: tuple = ()) -> Any:
        cur = self._conn.execute(sql, params)
        return cur

    def write(self, item: MemoryItem) -> str:
        self._execute(
            """
            INSERT INTO agent_memory
                (memory_id, kind, namespace, payload, dataset_hash, run_id, created_at)
            VALUES (%s, %s, %s, %s::jsonb, %s, %s, %s)
            ON CONFLICT (memory_id) DO UPDATE SET payload = EXCLUDED.payload
            """,
            (
                item.memory_id,
                item.kind.value,
                ",".join(item.namespace),
                _to_dict(item),
                item.dataset_hash,
                item.run_id,
                item.created_at,
            ),
        )
        self._conn.commit()
        return item.memory_id

    def get(self, memory_id: str) -> MemoryItem | None:
        rows = self._execute(
            "SELECT payload FROM agent_memory WHERE memory_id = %s", (memory_id,)
        ).fetchall()
        if not rows:
            return None
        return _from_dict(dict(rows[0][0]))

    def query(
        self,
        namespace: tuple[str, str, str],
        kind: MemoryKind | None = None,
        top_k: int = 5,
    ) -> list[MemoryItem]:
        ns = ",".join(namespace)
        if kind is not None:
            rows = self._execute(
                "SELECT payload FROM agent_memory WHERE namespace = %s AND kind = %s "
                "ORDER BY created_at DESC LIMIT %s",
                (ns, kind.value, top_k),
            ).fetchall()
        else:
            rows = self._execute(
                "SELECT payload FROM agent_memory WHERE namespace = %s "
                "ORDER BY created_at DESC LIMIT %s",
                (ns, top_k),
            ).fetchall()
        return [_from_dict(dict(r[0])) for r in rows]

    def invalidate(self, memory_id: str, invalidated_at: float | None = None) -> None:
        import time

        ts = invalidated_at if invalidated_at is not None else time.time()
        self._execute(
            "UPDATE agent_memory SET payload = jsonb_set(payload, %s, %s::jsonb) "
            "WHERE memory_id = %s",
            ("{invalidated_at}", str(ts), memory_id),
        )
        self._conn.commit()

    def list_by_run(self, run_id: str) -> list[MemoryItem]:
        rows = self._execute(
            "SELECT payload FROM agent_memory WHERE run_id = %s ORDER BY created_at",
            (run_id,),
        ).fetchall()
        return [_from_dict(dict(r[0])) for r in rows]

    def delete_run(self, run_id: str) -> list[str]:
        items = self.list_by_run(run_id)
        self._execute("DELETE FROM agent_memory WHERE run_id = %s", (run_id,))
        self._conn.commit()
        return [item.memory_id for item in items]

    def close(self) -> None:
        self._conn.close()
