# Third-party software and research attribution

MORPHPROOF's own source is licensed under its root LICENSE. Dependencies and retained upstream fixtures keep their original licenses. A citation is not permission to copy code: retain applicable notices and license text when redistributing source or binaries.

## Retained upstream fixtures

The project retains unmodified source modules and license files for two independently selected function-level experiments:

| Retained material | Original project and revision | License and notices |
| --- | --- | --- |
| `experiments/upstream/more_itertools/recipes.py` | [more-itertools](https://github.com/more-itertools/more-itertools/tree/4aeb4338ae1407d8da9723e86da99efeb446f719) | [Original MIT license](../experiments/upstream/more_itertools/LICENSE), copyright 2012 Erik Rose. The module documents its Python itertools-recipes lineage. |
| `experiments/upstream/boltons/statsutils.py` | [boltons](https://github.com/mahmoud/boltons/tree/d31d821d56c8f7756af9c30a864077f2e5855321) | [Original BSD-3-Clause license](../experiments/upstream/boltons/LICENSE), copyright 2013 Mahmoud Hashemi. The source header also retains its original notice. |

[Fixture provenance](../experiments/upstream/provenance.json) records exact source URLs and hashes. MORPHPROOF's thin adapter files are identified separately. No upstream endorsement is implied.

## Toolchain and declared optional packages

Installation resolves these projects independently. Refer to the installed distribution metadata and dependency lockfiles or build records for the exact versions used in a given run.

| Project | Role | Upstream license |
| --- | --- | --- |
| [CPython](https://github.com/python/cpython/blob/main/LICENSE) | Python runtime and standard library | PSF license and incorporated third-party notices |
| [Rust](https://github.com/rust-lang/rust/blob/master/COPYRIGHT) | Native compiler and standard library for transformations | Primarily MIT / Apache-2.0; see upstream notices |
| [setuptools](https://github.com/pypa/setuptools/blob/main/LICENSE) | Python packaging build backend | MIT |
| [pytest](https://github.com/pytest-dev/pytest/blob/main/LICENSE) | Optional test runner | MIT |
| [Hypothesis](https://github.com/HypothesisWorks/hypothesis/blob/master/LICENSE.txt) | Optional property-based testing and evaluation | MPL-2.0, except separately noted source |
| [Maturin](https://github.com/PyO3/maturin#license) | Optional Rust-backed package build tooling | MIT / Apache-2.0, at the user's option |
| [PyO3](https://github.com/PyO3/pyo3#license) | Generated Python/Rust bindings | MIT / Apache-2.0 |

Hypothesis remains a separately installed package; its MPL license does not replace the license of MORPHPROOF's original files. If modifying or vendoring a dependency, comply with that dependency's source and notice requirements.

Research references and design context are documented in [research foundations](research.md).
