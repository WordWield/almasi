# Almasi

**Import a library that isn't installed. Extend an entire library, not just a class. Create Python objects that remember their state after your program exits.**

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

## Start small. Grow naturally.

One small installation. Composable libraries. Persistent objects. A foundation for applications, developer tools and intelligent systems that evolve without accumulating unnecessary machinery.

> **Complexity emerging from necessity, not accumulation.**

Python 3.11+ · Apache-2.0 · Actively developed open-source software.

**A note on automatic updates:** Git and pip must be available. Libraries are acquired from trusted Git repositories and execute Python code in the active environment. Updates follow the upstream branch when fast-forwarding is possible; this is not a pinned dependency resolver or a sandbox. First acquisition requires access to the repository. See the [loader documentation](https://github.com/WordWield/almasi/blob/master/docs/loader.md) for configuration and update behavior.

[Core source](https://github.com/WordWield/almasi.a) · [O source](https://github.com/WordWield/almasi.o) · [Almasi source](https://github.com/WordWield/almasi)
