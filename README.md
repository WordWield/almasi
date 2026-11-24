# Almasi

**Import a library that isn't installed. Extend an entire library, not just a class. Create Python objects that survive restarts and react to changes in other processes.**

Almasi is a different approach to building Python software: less wiring, fewer duplicate representations, more room to grow.

```bash
pip install almasi
```

```python
from almasi import a, o
```

That's all you need to acquire [Almasi Core](https://github.com/WordWield/almasi.a) and [Almasi O](https://github.com/WordWield/almasi.o). Missing libraries arrive on demand, their dependencies are installed automatically, and existing Git checkouts are checked for updates on first use in each new process. No separate installation commands for each library.

## 1. Your filesystem becomes your architecture

Create a directory with these three files:

```text
studio.py
root/
├── greetings.py
└── settings.json
```

**studio.py**

```python
from almasi import a

studio = a.extend('studio')
```

**root/greetings.py**

```python
import studio


class Greetings(studio.Module):

	def hello(self):
		return 'Hello, Almasi!'
```

**root/settings.json**

```json
{"theme": "dark"}
```

Open Python in that directory:

```python
import studio

print(studio.Greetings().hello())  # Hello, Almasi!
print(studio.settings['theme'])   # dark
```

No component registration. No import lists. No configuration loader.

Add a component under `root/`, and it becomes available through the library's namespace when accessed. Nested directories become nested namespaces.

And because an Almasi library supports inheritance, another library can extend `studio` just as `studio` extends `a`. In its own `studio_pro.py` entry file, with its own sibling `root/` directory and `studio` on the Python import path:

```python
import studio

studio_pro = studio.extend('studio_pro')
```

It inherits the parent's capabilities and can introduce its own components. **Extend the architecture instead of wiring it together again.**

[Explore Almasi Core →](https://github.com/WordWield/almasi.a)

## 2. A dictionary that remembers

In a fresh directory, create an empty `root/` folder and save this as `counter.py`:

```python
from almasi import o

counter = o.extend('counter')
o.start(sync=True)

if not hasattr(o.V, 'stats'):
	o.V.stats = {'visits': 0}

o.V.stats['visits'] += 1
print(o.V.stats['visits'])
```

Run the same program three times:

```text
$ python counter.py
1
$ python counter.py
2
$ python counter.py
3
```

An ordinary Python dictionary assigned to `o.V` becomes a persistent O dictionary. Its mutations survive process restarts. No serialization code, database queries or explicit save/load calls.

## 3. Validation, identity and persistence — one model

For typed objects, a single declaration is enough:

```python
Person = o.T.extend('Person', name=str, visits=int)
```

In an application with O started, this validates and converts field values both during construction and on assignment:

```python
person = Person(name='Ada', visits='1')
assert person.visits == 1

person.visits = '2'
assert person.visits == 2

person.visits = 'not a number'  # ValueError
```

Compare the equivalent basic field validation with assignment validation enabled in Pydantic v2:

```python
from pydantic import BaseModel, ConfigDict


class Person(BaseModel):
	model_config = ConfigDict(validate_assignment=True)

	name: str
	visits: int
```

O needs just one type declaration for this scenario. It also provides persistent identity, relationships and schema generation from the same definition. The comparison concerns basic field conversion and assignment validation, not the full range of Pydantic's validation features.

### One person, multiple references, across restarts

In another fresh directory, create an empty `root/` folder and save this as `memory.py`:

```python
from almasi import o

memory = o.extend('memory')
o.start(sync=True)

Person = o.T.extend('Person', name=str, visits=int)

if not hasattr(o.V, 'owner'):
	person     = Person(name='Ada', visits=0)
	o.V.owner  = person
	o.V.people = o.List([person])

o.V.people[0].visits += 1

assert o.V.owner.id == o.V.people[0].id
print(o.V.owner.name, o.V.owner.visits)
```

Run it twice:

```text
$ python memory.py
Ada 1

$ python memory.py
Ada 2
```

Two paths through the object graph refer to the same persistent person. Change the person through one reference and read the change through another — even after the program has exited and restarted.

**No save(). No load(). No ORM mapping.** Just Python objects, with persistent identity.

The same type definition can also generate a JSON Schema:

```python
print(Person.to_json_schema())
```

The same model can serve as application state, a schema and structured AI-facing data. O also supports sharing a persistent ontology between processes with explicit multiprocess startup.

[Explore Almasi O →](https://github.com/WordWield/almasi.o)

## 4. Two processes. One living object graph.

**Change a Python dictionary in one terminal. Watch the other terminal react.**

In a fresh directory with an empty `root/` folder, save this as `live.py`:

```python
import sys

from almasi import o

live = o.extend('live')
o.start(sync=True, multiprocess=True)

if not hasattr(o.V, 'stats'):
	o.V.stats = {'visits': 0}

stats = o.V.stats

if sys.argv[1] == 'watch':
	cancel = o.services.Sync.subscribe(
		{stats.id},
		lambda ids: print(stats['visits'], flush=True)
	)

	try:
		print(stats['visits'], flush=True)
		input('Press Enter to stop.\n')
	finally:
		cancel()
else:
	stats['visits'] += 1
	input('Press Enter after the watcher receives the update.\n')
```

In terminal A, run `python live.py watch` and wait for the initial value. In terminal B, from the same directory, run `python live.py write`.

Terminal A:

```text
$ python live.py watch
0
Press Enter to stop.
1
2
```

The last two values appear after two separate runs of the writer. No polling. No external message broker. No manually synchronized cache. Even the watcher's existing `stats` reference sees the new committed state.

O automatically invalidates affected cached entities before delivering remote notifications. Subscribe to specific object IDs or observe all changes. Both processes use the same persistent ontology, not two copies of the data.

Local and cross-process notifications share the same subscription API. O starts its host-local notification transport automatically when requested.

Notifications are asynchronous invalidation hints, can be coalesced, and are not a durable event log. The writer in this example stays alive until the watcher receives the notification. The processes share a database on one machine; this is not cross-host replication.

[Subscriptions and synchronization →](https://github.com/WordWield/almasi.o/blob/master/docs/architecture.sync.md)

## 5. Object semantics, without giving up fast reads

O is backed by LMDB. In a November 2026 local benchmark, reading a persistent list element took **1.09 µs**, compared with **1.59 µs** for an indexed SQLite row read — about 1.46× faster in that workload.

| Operation | O (µs) | SQLite (µs) |
| --- | ---: | ---: |
| Indexed list read | 1.089 | 1.593 |
| Keyed dictionary read | 2.061 | 1.680 |
| List element write | 59.191 | 5.952 |
| Dictionary element write | 65.248 | 5.309 |

In a separate November 24 CI benchmark, O's cached object-attribute reads measured **28 ns**. List and dictionary reads measured 0.619 µs and 1.295 µs respectively.

Fast reads are only part of the story: O also maintains persistent types, object identity and references. Writes are currently substantially more expensive than SQLite's indexed row updates. O is designed for expressive persistent object graphs, not as a universally faster SQL replacement.

The direct comparison used Python 3.11.14, SQLite 3.51.1, macOS arm64, 5,000 iterations, LMDB sync=False and SQLite WAL synchronous=OFF in autocommit mode, with one commit per write and fixture creation excluded. Neither configuration guarantees durability across power loss. The separate cached-read figures are from Python 3.12 on GitHub Actions Ubuntu, five rounds of 1,000 iterations; they are not a direct SQLite comparison.

[Reproduce the SQLite comparison](https://github.com/WordWield/almasi.o/blob/master/root/tests/_test_performance_sqlite_compare.py) · [Published O performance results](https://github.com/WordWield/almasi.o/blob/master/docs/performance.txt)

## Start small. Grow naturally.

One small installation. Composable libraries. Persistent objects. Live shared state. A foundation for applications, developer tools and intelligent systems that evolve without accumulating unnecessary machinery.

> **Complexity emerging from necessity, not accumulation.**

**Discover more about Almasi and the vision behind it at [wordwield.ai](https://wordwield.ai).**

Python 3.11+ · Apache-2.0 · Actively developed open-source software.

**A note on automatic updates:** Git and pip must be available. Libraries are acquired from trusted Git repositories and execute Python code in the active environment. Updates follow the upstream branch when fast-forwarding is possible; this is not a pinned dependency resolver or a sandbox. First acquisition requires access to the repository. See the [loader documentation](https://github.com/WordWield/almasi/blob/master/docs/loader.md) for configuration and update behavior.

[Core source](https://github.com/WordWield/almasi.a) · [O source](https://github.com/WordWield/almasi.o) · [Almasi source](https://github.com/WordWield/almasi)
