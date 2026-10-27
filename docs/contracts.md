# The supported contract

Version 0.1 accepts a file with pure deterministic public numerical functions,
each taking one positional or named `list[float]` parameter and returning a float.
The initial compiler accepts float local assignments, ordered loops over the list
or constant slices, constant indexing, `+ - * /`, `abs`, `len`, numeric comparisons,
boolean conditions, `if`, and literal supported exceptions. Unsupported syntax
fails before output generation; there is no fallback to Python.

The independent verifier also compares Python candidates outside the compiler's
syntax subset, provided their observable API fits the declared domain. It compares
return types, binary64 values, signed zero, infinities, NaN class, and exception
type/message. Tolerances default to exact equality and may only be explicitly
changed in the user-reviewed contract. NaN payload bits, traceback text, timing,
side effects, object identity and undocumented exports are outside this contract.

```json
{
  "schema": 1,
  "functions": [{
    "name": "energy", "parameter": "values",
    "input": "list[float]", "output": "float",
    "max_length": 256, "rtol": 0.0, "atol": 0.0
  }]
}
```

`max_length` bounds generated input length, not a runtime guard on the resulting
package. Floats include NaN and infinity unless `allow_nonfinite: false` is
explicitly declared. Integers, mixed types, custom sequences, multiple arguments,
stateful functions, imports and dynamic dispatch are not compiler claims. The
Python wrapper preserves the declared parameter name; three keyword-call checks
supplement the main positional test budget. Missing/default/extra arguments and
reflection details are not covered.

`morphproof discover module.py -o contract.json` inventories one-argument public
function signatures and proposes this bounded domain. Review it before use.
Discovery does not infer the actual type contract or prove documentation.

# Evidence accounting

`--budget N` means N differential pairs per function. Each pair invokes one
reference and one candidate. Each function has up to 128 additional minimization
pairs and three named-call checks, reported separately. Test selection uses only
source structure and reference coverage/outcomes; candidate outputs cannot steer
acceptance. Every generated challenge and observed result is saved in
`tested-cases.json`. A 3-second per-response timeout marks infrastructure errors
as `error`, never as a successful compatibility result.

The original and candidate module bytes are captured and hashed. For generated
Rust candidates, `morphproof-build.json` lists the native binary, Rust source and
build metadata; their hashes must remain unchanged throughout verification.
Imported dependencies beyond that declared set are not frozen. Record your lock
files and environment when reviewing a production transformation.

Finite tests give evidence for sampled inputs. No universal proof or symbolic
certificate is produced in this release. CrossHair and formal tools may add
specific properties later; they do not justify claims about untested native code.
