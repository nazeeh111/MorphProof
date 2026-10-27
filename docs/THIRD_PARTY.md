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

Hypothesis remains a separately installed package; its MPL license does not replace the license of MORPHPROOF's original files. If modifying or vendoring a dependency, comply with that dependency's source and notice requirements.

## Investigated foundations

The following informed design choices or were evaluated as possible tools. Research discussion does not mean their code was copied, executed or included as a dependency:

- [Harvest Agentic Translator](https://github.com/UW-HARVEST/harvest-agentic), MIT as identified by its repository. External upstream-test grading is a relevant precedent.
- [RustPrint](https://arxiv.org/abs/2605.14634v3), by Minh Le-Anh, Anh Nguyen Hoang, Bach Le and Nghi D. Q. Bui. Documentation-guided C-to-Rust migration research; cite the paper for its results.
- [CrossHair](https://github.com/pschanely/CrossHair/blob/master/LICENSE), primarily MIT, with Apache and PSF licensed incorporated material. Its limitations inform the boundary between testing and proof.
- [PyO3](https://github.com/PyO3/pyo3#license), MIT / Apache-2.0. Mature Python/Rust binding technology.
- [Tree-sitter](https://github.com/tree-sitter/tree-sitter/blob/master/LICENSE), MIT. Multi-language parsing was considered; Python-only discovery can use the standard library.
- [C2Rust](https://github.com/immunant/c2rust/blob/master/docs/cross-check-tutorial.md), [Syzygy](https://syzygy-project.github.io/) and [RustAssure](https://arxiv.org/abs/2510.07604) establish earlier differential/symbolic migration-verification work.
- [py2many](https://github.com/py2many/py2many), MIT as identified by its repository, is prior Python-to-Rust transpilation work.
- [PaperVizAgent](https://github.com/google-research/papervizagent/blob/main/LICENSE), Apache-2.0. Investigated for technical visual production; its model-key/cloud workflow is not a requirement for MORPHPROOF.
- [/brag](https://github.com/latent-spaces/brag), MIT for its code. Its bundled media have separate attributions, including CC BY 4.0 music. Investigating or using a workflow does not grant permission to omit media credits. Retain media-specific credits if those assets are used.

See [research foundations](research.md) for design implications and limits. Final benchmark results must cite actual recorded executions, not upstream authors' performance claims.
